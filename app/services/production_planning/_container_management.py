"""
Container Management for Production Planning

Single purpose: Find suitable containers, convert capacities, and provide greedy fill strategy.
"""

import logging
import math
from typing import List, Optional, Dict, Any, Tuple
from flask_login import current_user
from ...models import Recipe, InventoryItem

logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    api_format: bool = True,
    product_density: Optional[float] = None,
    fill_pct: Optional[float] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Single entry point for container analysis.

    Returns:
        - Container strategy (greedy fill selection)
        - All available container options
    """
    try:
        org_id = organization_id or (current_user.organization_id if current_user.is_authenticated else None)
        if not org_id:
            raise ValueError("Organization ID required")

        # Get recipe requirements
        if recipe is None:
            raise ValueError("Recipe is required for container analysis")
        total_yield = (getattr(recipe, 'predicted_yield', 0) or 0) * scale
        yield_unit = getattr(recipe, 'predicted_yield_unit', None) or 'ml'
        # Apply recipe-level vessel fill % if present and valid
        try:
            recipe_fill_pct = None
            cd = getattr(recipe, 'category_data', None)
            if isinstance(cd, dict):
                vfp = cd.get('vessel_fill_pct')
                if vfp is not None:
                    recipe_fill_pct = float(vfp)
        except Exception:
            recipe_fill_pct = None

        if total_yield <= 0:
            raise ValueError(f"Recipe '{recipe.name}' has no predicted yield configured")

        # Load and filter containers
        container_options, conversion_failures = _load_suitable_containers(
            recipe, org_id, total_yield, yield_unit, product_density
        )

        if not container_options:
            if conversion_failures and api_format:
                # Check if this is a yield container mismatch
                has_mismatch_error = any(
                    failure.get('error_code') == 'YIELD_CONTAINER_MISMATCH'
                    for failure in conversion_failures
                )
                
                if has_mismatch_error:
                    from .drawer_errors import generate_drawer_payload_for_container_error
                    drawer_payload = generate_drawer_payload_for_container_error(
                        error_code='YIELD_CONTAINER_MISMATCH',
                        recipe=recipe,
                        mismatch_context={
                            'yield_unit': yield_unit,
                            'failures': conversion_failures
                        }
                    )
                    strategy = {
                        'success': False,
                        'requires_drawer': True,
                        'drawer_payload': drawer_payload,
                        'error': f"No containers match the recipe yield unit ({yield_unit}).",
                        'error_code': 'YIELD_CONTAINER_MISMATCH',
                        'status': 'error',
                        'container_options': [],
                        'yield_amount': total_yield,
                        'yield_unit': yield_unit
                    }
                    return strategy, []

            raise ValueError(
                f"No containers with valid capacity data found for recipe '{recipe.name}'. "
                f"Ensure containers have capacity unit values convertible to {yield_unit}."
            )

        # Create greedy fill strategy
        # Determine effective fill pct (prefer recipe, otherwise client-provided)
        effective_fill_pct = None
        for_candidate = fill_pct
        if recipe_fill_pct and recipe_fill_pct > 0:
            effective_fill_pct = recipe_fill_pct
        elif for_candidate is not None:
            try:
                effective_fill_pct = float(for_candidate)
            except Exception:
                effective_fill_pct = None

        strategy = _create_greedy_strategy(container_options, total_yield, yield_unit, effective_fill_pct)

        return strategy, container_options

    except MissingProductDensityError as e:
        # Structured drawer response for missing product density
        logger.warning(f"Container analysis requires product density for recipe {recipe.id}: {e}")
        if api_format:
            # Return a strategy payload that instructs FE to open a drawer
            from .drawer_errors import generate_drawer_payload_for_container_error
            drawer_payload = generate_drawer_payload_for_container_error(
                error_code='MISSING_PRODUCT_DENSITY',
                recipe=recipe,
                from_unit=e.from_unit,
                to_unit=e.to_unit
            )

            strategy = {
                'success': False,
                'requires_drawer': True,
                'drawer_payload': drawer_payload,
                'error': 'Product density required to convert between units',
                'status': 'error',
                'yield_amount': total_yield,
                'yield_unit': yield_unit,
                'container_options': []
            }

            return strategy, []
        raise
    except Exception as e:
        rid = getattr(recipe, 'id', 'unknown')
        logger.error(f"Container analysis failed for recipe {rid}: {e}")
        if api_format:
            return None, []
        raise


def _load_suitable_containers(
    recipe: Recipe,
    org_id: int,
    total_yield: float,
    yield_unit: str,
    product_density: Optional[float]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load containers allowed for this recipe and convert capacities"""

    # Get recipe's allowed containers - Recipe model uses 'allowed_containers' field
    allowed_container_ids = getattr(recipe, 'allowed_containers', [])

    if not allowed_container_ids:
        raise ValueError(f"Recipe '{recipe.name}' has no containers configured")

    # Load containers from database in one query (avoid N+1)
    containers = InventoryItem.query.filter(
        InventoryItem.id.in_(allowed_container_ids),
        InventoryItem.organization_id == org_id,
        InventoryItem.quantity > 0
    ).all()

    container_options = []
    conversion_failures: List[Dict[str, Any]] = []

    for container in containers:
        # Get container capacity
        storage_capacity = getattr(container, 'capacity', None)
        storage_unit = getattr(container, 'capacity_unit', None)

        if not storage_capacity or not storage_unit:
            logger.warning(f"Container {container.name} missing capacity data - skipping")
            continue

        # Convert capacity to recipe yield units
        converted_capacity, conversion_issue = _convert_capacity(
            storage_capacity, storage_unit, yield_unit, product_density, recipe
        )
        if conversion_issue:
            conversion_failures.append({
                'container_id': container.id,
                'container_name': container.container_display_name,
                'from_unit': storage_unit,
                'to_unit': yield_unit,
                'error_code': conversion_issue.get('error_code'),
                'error_message': conversion_issue.get('error_message')
            })
            continue
        if converted_capacity <= 0:
            logger.warning(f"Container {container.name} capacity conversion failed - skipping")
            continue

        container_options.append({
            'container_id': container.id,
            'container_name': container.container_display_name,
            'capacity': converted_capacity,  # Always in recipe yield units before fill %
            'capacity_in_yield_unit': converted_capacity,  # Explicit for frontend
            'yield_unit': yield_unit,  # Add yield unit for frontend
            'conversion_successful': True,  # Mark conversion as successful
            'original_capacity': storage_capacity,
            'original_unit': storage_unit,
            'available_quantity': int(container.quantity or 0),
            'containers_needed': 0,  # Will be set by strategy
            'cost_each': 0.0
        })

    # Sort by capacity (largest first for greedy algorithm)
    container_options.sort(key=lambda x: x['capacity'], reverse=True)

    # Check if we have any valid containers after filtering
    if not container_options and not conversion_failures:
        logger.warning(f"Recipe '{recipe.name}' has {len(containers)} containers configured, but none have valid capacity data or are convertible to {yield_unit}")
        # Return empty list instead of raising error - let caller handle

    # Check if any containers have units that directly match the yield unit
    compatible_containers = []
    for container in containers:
        storage_unit = getattr(container, 'capacity_unit', None)
        if storage_unit == yield_unit:
            compatible_containers.append(container)

    # If no compatible containers AND we have conversion failures, 
    # this indicates a unit mismatch rather than missing density
    if not compatible_containers and conversion_failures:
        # Check if all conversion failures are due to missing density
        all_missing_density = all(
            failure.get('error_code') == 'MISSING_DENSITY' 
            for failure in conversion_failures
        )
        
        if all_missing_density:
            # This is a unit mismatch case - containers exist but can't convert to yield unit
            logger.warning(f"Unit mismatch: No containers found with yield unit {yield_unit} for recipe {recipe.id}")
            conversion_failures.append({
                'container_id': None,
                'container_name': 'Unit Mismatch',
                'from_unit': 'mixed',
                'to_unit': yield_unit,
                'error_code': 'YIELD_CONTAINER_MISMATCH',
                'error_message': f'No containers match recipe yield unit {yield_unit}'
            })

    return container_options, conversion_failures


def _convert_capacity(
    capacity: float,
    from_unit: str,
    to_unit: str,
    product_density: Optional[float],
    recipe: Recipe
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """Convert container capacity to recipe yield units.

    If a cross-type conversion (volume ↔ weight) is required and no product_density
    is provided, raise a MissingProductDensityError to trigger the drawer protocol.
    """
    if from_unit == to_unit:
        return capacity, None

    try:
        from ...services.unit_conversion import ConversionEngine
        # Attempt conversion with provided product density if any
        result = ConversionEngine.convert_units(capacity, from_unit, to_unit, density=product_density)

        if isinstance(result, dict):
            if result.get('success'):
                return float(result.get('converted_value', 0.0)), None
            # Detect missing density from conversion engine
            if result.get('error_code') == 'MISSING_DENSITY':
                raise MissingProductDensityError(from_unit=from_unit, to_unit=to_unit)

            logger.warning(f"Capacity conversion failed {from_unit}->{to_unit}: {result}")
            return 0.0, {
                'error_code': result.get('error_code') or 'CONVERSION_ERROR',
                'error_message': (result.get('error_data') or {}).get('message') or result.get('error_message'),
                'from_unit': from_unit,
                'to_unit': to_unit
            }

        # Primitive return
        return float(result), None
    except MissingProductDensityError:
        # Bubble up for the caller to construct a drawer payload
        raise
    except Exception as e:
        logger.warning(f"Cannot convert {capacity} {from_unit} to {to_unit}: {e}")
        return 0.0, {
            'error_code': 'CONVERSION_EXCEPTION',
            'error_message': str(e),
            'from_unit': from_unit,
            'to_unit': to_unit
        }


class MissingProductDensityError(Exception):
    def __init__(self, from_unit: str, to_unit: str):
        super().__init__(f"Missing product density for conversion {from_unit} -> {to_unit}")
        self.from_unit = from_unit
        self.to_unit = to_unit


def _create_greedy_strategy(container_options: List[Dict[str, Any]], total_yield: float, yield_unit: str, fill_pct: Optional[float] = None) -> Dict[str, Any]:
    """Create greedy fill strategy - largest containers first"""

    selected_containers = []
    remaining_yield = total_yield

    for container in container_options:
        if remaining_yield <= 0:
            break

        # Determine effective capacity with optional fill %
        effective_capacity = container['capacity']
        if fill_pct and fill_pct > 0:
            effective_capacity = container['capacity'] * (fill_pct / 100.0)
        if effective_capacity <= 0:
            continue

        # Calculate how many of this container we need
        containers_needed = min(
            container['available_quantity'],
            math.ceil(remaining_yield / effective_capacity)
        )

        if containers_needed > 0:
            # Update the container option with selection
            # copy and record effective capacity for UI
            ccopy = container.copy()
            ccopy['containers_needed'] = containers_needed
            ccopy['effective_capacity'] = effective_capacity
            selected_containers.append(ccopy)
            remaining_yield -= containers_needed * effective_capacity

    # Calculate totals
    total_capacity = sum((c.get('effective_capacity', c['capacity'])) * c['containers_needed'] for c in selected_containers)

    # Local optimization around greedy solution to reduce overfill and improve containment
    def _optimize_selection(options: List[Dict[str, Any]], base_selection: List[Dict[str, Any]], target_yield: float) -> List[Dict[str, Any]]:
        # Consider only top K options for tractability
        top_options = options[:min(3, len(options))]
        # Build base counts map
        base_counts = {c['container_id']: c['containers_needed'] for c in base_selection}

        # Build search ranges near base counts
        ranges = []
        for opt in top_options:
            base = base_counts.get(opt['container_id'], 0)
            lo = max(0, base - 2)
            hi = min(opt['available_quantity'], base + 2)
            ranges.append((opt, range(lo, hi + 1)))

        best_combo = None
        best_capacity = 0.0
        target_min = target_yield * 0.97  # within 3% tolerance counts as contained

        # Nested loops up to 5^3 = 125 combos
        def _search(idx: int, current_counts: Dict[int, int]):
            nonlocal best_combo, best_capacity
            if idx == len(ranges):
                # Compute capacity of considered set; include counts of non-top options from base
                capacity = 0.0
                # top options
                for opt, _ in ranges:
                    eff_cap = opt.get('effective_capacity', opt['capacity'])
                    capacity += current_counts.get(opt['container_id'], 0) * eff_cap
                # other options from base selection unchanged
                for c in base_selection:
                    if c['container_id'] not in current_counts:
                        eff_cap2 = c.get('effective_capacity', c['capacity'])
                        capacity += c['containers_needed'] * eff_cap2

                # Feasibility preference: prefer >= target_min and minimize overfill; otherwise maximize capacity
                if capacity >= target_min:
                    if best_combo is None or (best_capacity < target_min) or (capacity < best_capacity):
                        best_combo = current_counts.copy()
                        best_capacity = capacity
                else:
                    if best_combo is None or best_capacity < target_min or capacity > best_capacity:
                        best_combo = current_counts.copy()
                        best_capacity = capacity
                return

            opt, rng = ranges[idx]
            for cnt in rng:
                current_counts[opt['container_id']] = cnt
                _search(idx + 1, current_counts)
            # cleanup
            current_counts.pop(opt['container_id'], None)

        _search(0, {})

        # Build new selection list
        new_selection_map = {c['container_id']: c.copy() for c in base_selection}
        # update counts for top options
        for opt, _ in ranges:
            cnt = best_combo.get(opt['container_id'], 0) if best_combo else base_counts.get(opt['container_id'], 0)
            if opt['container_id'] in new_selection_map:
                new_selection_map[opt['container_id']]['containers_needed'] = cnt
            else:
                if cnt > 0:
                    new_selection_map[opt['container_id']] = {
                        **opt,
                        'containers_needed': cnt
                    }
        # remove zero-count entries
        new_selection = [c for c in new_selection_map.values() if c['containers_needed'] > 0]
        return new_selection

    if selected_containers:
        optimized = _optimize_selection(container_options, selected_containers, total_yield)
        # Recompute totals
        total_capacity = sum((c.get('effective_capacity', c['capacity'])) * c['containers_needed'] for c in optimized)
        selected_containers = optimized

    # Containment = Can the total capacity hold the yield?
    # Show 100% if within 3% tolerance (97% or above)
    if total_yield > 0:
        raw_containment = (total_capacity / total_yield) * 100
        # If we have 97% or more capacity, show as 100% contained
        if raw_containment >= 97.0:
            containment_percentage = 100.0
        else:
            containment_percentage = raw_containment
    else:
        containment_percentage = 100.0 if total_capacity > 0 else 0.0

    # Create warnings - separate containment from fill efficiency
    warnings = []
    containment_warnings = []
    fill_efficiency_warnings = []

    # CONTAINMENT WARNINGS (critical - can we hold the batch?)
    if remaining_yield > 0:
        containment_warnings.append(f"Insufficient capacity: {remaining_yield:.1f} {yield_unit} remaining")

    # FILL EFFICIENCY WARNINGS (optimization - how well are containers used?)
    if selected_containers and total_capacity > 0 and remaining_yield <= 0:  # Only if contained
        # Calculate fill efficiency of the last container
        last_container = selected_containers[-1]

        # Calculate how much yield goes into each container type
        remaining_yield_to_allocate = total_yield

        for i, container in enumerate(selected_containers):
            if i == len(selected_containers) - 1:  # Last container type
                # For the last container type, calculate partial fill
                full_containers_of_this_type = container['containers_needed'] - 1
                yield_in_full_containers = full_containers_of_this_type * container['capacity']
                remaining_yield_to_allocate -= yield_in_full_containers

                # The remaining yield goes into the final container
                if remaining_yield_to_allocate > 0 and container['capacity'] > 0:
                    last_container_fill_percentage = (remaining_yield_to_allocate / container['capacity']) * 100

                    # Apply fill efficiency rules
                    if last_container_fill_percentage < 100:
                        if last_container_fill_percentage < 75:
                            fill_efficiency_warnings.append(f"Partial fill warning: last container will be filled {last_container_fill_percentage:.1f}% - consider using other containers")
                        else:
                            fill_efficiency_warnings.append(f"Last container partially filled to {last_container_fill_percentage:.1f}%")
                break
            else:
                # For non-last containers, all are filled completely
                yield_in_this_container_type = container['containers_needed'] * container['capacity']
                remaining_yield_to_allocate -= yield_in_this_container_type

    # Combine all warnings
    warnings.extend(containment_warnings)
    warnings.extend(fill_efficiency_warnings)

    return {
        'success': True,
        'container_selection': selected_containers,
        'total_capacity': total_capacity,
        'containment_percentage': containment_percentage,
        'warnings': warnings,
        'strategy_type': 'greedy_fill_optimized'
    }