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
    recipe, scale: float, preferred_container_id: int = None, organization_id: int = None
):
    """
    Analyze container options for a recipe at a given scale.
    Returns (strategy, options) where strategy is 'all_containers' and options is ALL allowed containers.
    """
    try:
        logger.info(f"🏭 CONTAINER ANALYSIS: Starting analysis for recipe {recipe.id if recipe else 'None'}, scale {scale}")

        if not recipe:
            logger.warning("🏭 CONTAINER ANALYSIS: No recipe provided")
            return "all_containers", []

        # Get organization context
        if not organization_id and current_user and current_user.is_authenticated:
            organization_id = current_user.organization_id

        if not organization_id:
            logger.warning("🏭 CONTAINER ANALYSIS: No organization context")
            return "all_containers", []

        # Calculate total yield needed
        base_yield = recipe.predicted_yield or 0
        total_yield_needed = base_yield * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'

        logger.info(f"🏭 CONTAINER ANALYSIS: Total yield needed: {total_yield_needed} {yield_unit}")

        # Get allowed containers for this recipe
        allowed_container_ids = []
        if recipe.allowed_containers:
            try:
                # Handle different formats of allowed_containers
                if isinstance(recipe.allowed_containers, str):
                    import json
                    allowed_container_ids = json.loads(recipe.allowed_containers)
                elif isinstance(recipe.allowed_containers, list):
                    allowed_container_ids = recipe.allowed_containers
                elif hasattr(recipe.allowed_containers, '__iter__'):
                    # Handle pickled lists or other iterables
                    allowed_container_ids = list(recipe.allowed_containers)
                else:
                    logger.warning(f"🏭 CONTAINER ANALYSIS: Unknown allowed_containers type: {type(recipe.allowed_containers)}")
                    allowed_container_ids = []

                # Convert to integers and filter out any invalid IDs
                allowed_container_ids = [int(id) for id in allowed_container_ids if str(id).isdigit()]
                logger.info(f"🏭 CONTAINER ANALYSIS: Recipe allows containers: {allowed_container_ids}")
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning(f"🏭 CONTAINER ANALYSIS: Invalid allowed_containers format: {recipe.allowed_containers}, error: {e}")

        if not allowed_container_ids:
            logger.warning("🏭 CONTAINER ANALYSIS: No allowed containers found for recipe")
            return "all_containers", []

        # Get available containers from inventory
        from app.models import InventoryItem
        available_containers = InventoryItem.query.filter(
            InventoryItem.id.in_(allowed_container_ids),
            InventoryItem.type == 'container',
            InventoryItem.organization_id == organization_id,
            InventoryItem.is_archived == False,
            InventoryItem.quantity > 0
        ).all()

        logger.info(f"🏭 CONTAINER ANALYSIS: Found {len(available_containers)} available containers")

        if not available_containers:
            logger.warning("🏭 CONTAINER ANALYSIS: No available containers in stock")
            return "all_containers", []

        # Return ALL allowed containers, not just greedy fill result
        all_container_options = []
        for container in available_containers:
            # Convert container capacity to recipe yield unit
            container_capacity_ml = container.storage_amount or 0

            # Convert to recipe yield unit if needed
            from app.services.unit_conversion import ConversionEngine
            try:
                conversion_result = ConversionEngine.convert_units(
                    amount=container_capacity_ml,
                    from_unit='ml',
                    to_unit=yield_unit,
                    ingredient_id=None
                )

                if conversion_result.get('success'):
                    container_capacity_yield_units = conversion_result['converted_value']
                    conversion_successful = True
                else:
                    # Fallback: assume ml = ml or 1:1 conversion
                    container_capacity_yield_units = container_capacity_ml
                    conversion_successful = False
                    logger.warning(f"🏭 CONTAINER ANALYSIS: Unit conversion failed for container {container.id}: {conversion_result.get('error_message', 'Unknown error')}")

            except Exception as e:
                logger.warning(f"🏭 CONTAINER ANALYSIS: Unit conversion exception for container {container.id}: {e}")
                container_capacity_yield_units = container_capacity_ml
                conversion_successful = False

            # Calculate how many containers would be needed
            containers_needed = math.ceil(total_yield_needed / container_capacity_yield_units) if container_capacity_yield_units > 0 else 0
            available_quantity = container.quantity

            all_container_options.append({
                'container_id': container.id,
                'container_name': container.name,
                'capacity': container_capacity_yield_units,
                'containers_needed': min(containers_needed, available_quantity),
                'total_capacity': container_capacity_yield_units * min(containers_needed, available_quantity),
                'available_quantity': available_quantity,
                'yield_unit': yield_unit,
                'original_capacity': container_capacity_ml,
                'original_unit': 'ml',
                'capacity_in_yield_unit': container_capacity_yield_units,
                'conversion_successful': conversion_successful,
                'cost_each': container.cost_per_unit or 0.0
            })

            logger.info(f"🏭 CONTAINER ANALYSIS: Available option: {container.name} (capacity: {container_capacity_yield_units} {yield_unit}, stock: {available_quantity})")

        # Sort by efficiency (fewer containers needed first)
        all_container_options.sort(key=lambda x: x['containers_needed'])

        logger.info(f"🏭 CONTAINER ANALYSIS: Returning {len(all_container_options)} container options")

        # Create greedy strategy for the best containers
        strategy_result = _create_greedy_strategy(all_container_options, total_yield_needed, yield_unit)

        # Always return strategy object for API compatibility
        return strategy_result

    except Exception as e:
        logger.error(f"🏭 CONTAINER ANALYSIS: Error during analysis: {e}")
        return {
            'success': False,
            'error': f'Container analysis failed: {str(e)}',
            'container_selection': [],
            'warnings': [str(e)]
        }


def _load_suitable_containers(recipe: Recipe, org_id: int, total_yield: float, yield_unit: str) -> List[Dict[str, Any]]:
    """Load containers allowed for this recipe and convert capacities"""

    # Get recipe's allowed containers - Recipe model uses 'allowed_containers' field
    allowed_container_ids = getattr(recipe, 'allowed_containers', [])

    # Debug logging to understand what's available
    logger.info(f"Recipe {recipe.id} container debug:")
    logger.info(f"  - allowed_containers: {allowed_container_ids}")
    logger.info(f"  - Recipe has allowed_containers field: {hasattr(recipe, 'allowed_containers')}")

    if not allowed_container_ids:
        raise ValueError(f"Recipe '{recipe.name}' has no containers configured")

    # Load containers from database in one query (avoid N+1)
    containers = InventoryItem.query.filter(
        InventoryItem.id.in_(allowed_container_ids),
        InventoryItem.organization_id == org_id,
        InventoryItem.quantity > 0
    ).all()

    container_options = []

    for container in containers:
        # Get container capacity
        storage_capacity = getattr(container, 'storage_amount', None)
        storage_unit = getattr(container, 'storage_unit', None)

        if not storage_capacity or not storage_unit:
            logger.warning(f"Container {container.name} missing capacity data")
            continue

        # Convert capacity to recipe yield units
        converted_capacity = _convert_capacity(storage_capacity, storage_unit, yield_unit)
        if converted_capacity <= 0:
            logger.warning(f"Container {container.name} capacity conversion failed")
            continue

        container_options.append({
            'container_id': container.id,
            'container_name': container.name,
            'capacity': converted_capacity,  # Always in recipe yield units
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

    return container_options


def _convert_capacity(capacity: float, from_unit: str, to_unit: str) -> float:
    """Convert container capacity to recipe yield units"""
    if from_unit == to_unit:
        return capacity

    try:
        from ...services.unit_conversion import ConversionEngine
        result = ConversionEngine.convert_units(capacity, from_unit, to_unit)
        return result['converted_value'] if isinstance(result, dict) else float(result)
    except Exception as e:
        logger.warning(f"Cannot convert {capacity} {from_unit} to {to_unit}: {e}")
        return 0.0


def _create_greedy_strategy(container_options: List[Dict[str, Any]], total_yield: float, yield_unit: str) -> Dict[str, Any]:
    """Create greedy fill strategy - largest containers first"""

    selected_containers = []
    remaining_yield = total_yield

    for container in container_options:
        if remaining_yield <= 0:
            break

        # Calculate how many of this container we need
        containers_needed = min(
            container['available_quantity'],
            math.ceil(remaining_yield / container['capacity'])
        )

        if containers_needed > 0:
            # Update the container option with selection
            container['containers_needed'] = containers_needed
            selected_containers.append(container.copy())
            remaining_yield -= containers_needed * container['capacity']

    # Calculate totals
    total_capacity = sum(c['capacity'] * c['containers_needed'] for c in selected_containers)

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

    # Calculate container fill metrics for frontend
    containment_metrics = {
        'is_contained': remaining_yield <= 0,
        'remaining_yield': remaining_yield if remaining_yield > 0 else 0,
        'yield_unit': yield_unit
    }

    # Calculate last container fill efficiency
    last_container_fill_metrics = None
    if selected_containers and total_capacity > 0 and remaining_yield <= 0:
        # Calculate how much yield goes into each container type (greedy algorithm)
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

                    last_container_fill_metrics = {
                        'container_name': container['container_name'],
                        'fill_percentage': round(last_container_fill_percentage, 1),
                        'is_partial': last_container_fill_percentage < 100,
                        'is_low_efficiency': last_container_fill_percentage < 75
                    }

                logger.info(f"Backend calculated last container fill: {last_container_fill_percentage:.1f}% for {container['container_name']}")
                break
            else:
                # For non-last containers, all are filled completely
                yield_in_this_container_type = container['containers_needed'] * container['capacity']
                remaining_yield_to_allocate -= yield_in_this_container_type

    return {
        'success': True,
        'container_selection': selected_containers,
        'available_containers': container_options,  # Include all available containers for manual selection
        'total_capacity': total_capacity,
        'containment_percentage': containment_percentage,
        'containment_metrics': containment_metrics,
        'last_container_fill_metrics': last_container_fill_metrics,
        'strategy_type': 'greedy_fill',
        'uses_greedy_algorithm': True,  # Confirms it mixes/matches containers optimally
        'warnings': []  # Empty - frontend will generate messages from metrics
    }