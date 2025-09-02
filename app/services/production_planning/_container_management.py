"""
Container Management for Production Planning

Handles container selection, capacity analysis, and optimal fill strategies.
Uses proper greedy algorithms for multi-container optimization.
"""

import logging
from decimal import Decimal, ROUND_UP
from typing import List, Tuple, Optional, Dict, Any

from app.models import Recipe, InventoryItem, IngredientCategory
from app.services.unit_conversion import ConversionEngine
from .types import ContainerOption, ContainerStrategy

# Import and clauses for filtering
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    organization_id: int,
    preferred_container_id: Optional[int] = None,
    api_format: bool = True
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Main entry point for container analysis.

    Returns:
        - strategy: Auto-fill strategy (dict format for API compatibility)
        - options: All available container options (list of dicts)
    """
    logger.info(f"CONTAINER_ANALYSIS: Starting analysis for recipe {recipe.id} ({recipe.name})")
    logger.info(f"CONTAINER_ANALYSIS: Parameters - scale: {scale}, org_id: {organization_id}, preferred: {preferred_container_id}")

    try:
        # Calculate target yield
        target_yield = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'count'

        logger.info(f"CONTAINER_ANALYSIS: Target yield calculated: {target_yield} {yield_unit}")

        if target_yield <= 0:
            logger.warning(f"CONTAINER_ANALYSIS: Invalid target yield {target_yield} - recipe yield: {recipe.predicted_yield}, scale: {scale}")
            return None, []

        # Get all valid containers
        logger.info("CONTAINER_ANALYSIS: Fetching valid containers...")
        container_options = _get_all_valid_containers(recipe, organization_id, target_yield, yield_unit)

        logger.info(f"CONTAINER_ANALYSIS: Found {len(container_options)} valid container options")

        if not container_options:
            logger.warning(f"CONTAINER_ANALYSIS: No valid containers found for recipe {recipe.id}")
            logger.info("CONTAINER_ANALYSIS: Debugging container search...")
            _debug_container_search(organization_id, yield_unit)
            return None, []

        # Log container options for debugging
        for i, opt in enumerate(container_options):
            logger.info(f"CONTAINER_ANALYSIS: Option {i+1}: {opt.container_name} - capacity: {opt.capacity} {yield_unit}, needed: {opt.containers_needed}")

        # Create auto-fill strategy using greedy algorithm
        logger.info("CONTAINER_ANALYSIS: Creating auto-fill strategy...")
        strategy = _create_auto_fill_strategy(container_options, target_yield)

        if strategy:
            logger.info(f"CONTAINER_ANALYSIS: Strategy created with {len(strategy.selected_containers)} container types")
            logger.info(f"CONTAINER_ANALYSIS: Total capacity: {strategy.total_capacity}, containment: {strategy.containment_percentage:.1f}%")
        else:
            logger.warning("CONTAINER_ANALYSIS: Failed to create strategy")

        # Convert to API format
        if api_format:
            strategy_dict = _strategy_to_dict(strategy) if strategy else None
            options_list = [_container_option_to_dict(opt) for opt in container_options]
            logger.info(f"CONTAINER_ANALYSIS: Returning API format - strategy: {strategy_dict is not None}, options: {len(options_list)}")
            return strategy_dict, options_list
        else:
            return strategy, container_options

    except Exception as e:
        logger.error(f"CONTAINER_ANALYSIS: Critical error in container analysis: {e}", exc_info=True)
        return None, []


def _get_all_valid_containers(
    recipe: Recipe,
    organization_id: int,
    target_yield: float,
    yield_unit: str
) -> List[ContainerOption]:
    """Get all containers that could potentially be used for this recipe"""
    try:
        # Get container category
        container_category = IngredientCategory.query.filter_by(
            name='Container',
            organization_id=organization_id
        ).first()

        if not container_category:
            logger.warning(f"No container category found for organization {organization_id}")
            return []

        # Get all containers in the organization
        containers = InventoryItem.query.filter_by(
            organization_id=organization_id,
            category_id=container_category.id
        ).all()

        if not containers:
            logger.warning(f"No containers found for organization {organization_id}")
            return []

        logger.info(f"CONTAINER_CONVERSION: Found {len(containers)} containers to process")

        valid_containers = []
        conversion_engine = ConversionEngine()

        for container in containers:
            try:
                logger.info(f"CONTAINER_VALIDATION: Processing container {container.name} (ID: {container.id})")

                # Get container capacity using the correct field names
                capacity_value = getattr(container, 'capacity', None)
                capacity_unit = getattr(container, 'capacity_unit', None)
                available_quantity = getattr(container, 'quantity', 0)

                logger.info(f"CONTAINER_VALIDATION: {container.name} - capacity: {capacity_value} {capacity_unit}, available: {available_quantity}")

                if not capacity_value or not capacity_unit:
                    logger.warning(f"CONTAINER_VALIDATION: {container.name} missing capacity/storage amount or unit")
                    continue

                if available_quantity <= 0:
                    logger.warning(f"CONTAINER_VALIDATION: {container.name} has no available quantity ({available_quantity})")
                    continue

                # Convert container capacity to recipe yield unit
                logger.info(f"CONTAINER_VALIDATION: Converting {capacity_value} {capacity_unit} to {yield_unit}")

                try:
                    conversion_result = conversion_engine.convert_units(
                        amount=float(capacity_value),
                        from_unit=capacity_unit,
                        to_unit=yield_unit
                    )
                    logger.info(f"CONTAINER_VALIDATION: Conversion result: {conversion_result}")
                except Exception as conv_error:
                    logger.warning(f"CONTAINER_VALIDATION: Conversion failed for {container.name}: {conv_error}")
                    continue

                # Validate conversion result structure
                if not isinstance(conversion_result, dict):
                    logger.warning(f"CONTAINER_VALIDATION: Invalid conversion result structure for container {container.name}: {conversion_result}")
                    continue

                if not conversion_result.get('success'):
                    logger.warning(f"CONTAINER_VALIDATION: Conversion failed for container {container.name}: {conversion_result.get('error_message', 'Unknown error')}")
                    continue

                # Extract converted capacity value correctly
                converted_capacity = conversion_result.get('converted_value')
                if converted_capacity is None or converted_capacity <= 0:
                    logger.warning(f"CONTAINER_VALIDATION: Invalid converted capacity for container {container.name}: {converted_capacity}")
                    continue

                # Calculate containers needed
                containers_needed = max(1, int((target_yield / converted_capacity) + 0.5))  # Round up
                total_capacity = converted_capacity * containers_needed
                fill_percentage = (target_yield / total_capacity) * 100

                logger.info(f"CONTAINER_VALIDATION: {container.name} - needs {containers_needed} containers, total capacity: {total_capacity}, fill: {fill_percentage:.1f}%")

                container_option = ContainerOption(
                    container_id=container.id,
                    container_name=container.name,
                    capacity=converted_capacity,
                    available_quantity=int(available_quantity),
                    containers_needed=containers_needed,
                    cost_each=getattr(container, 'cost_per_unit', 0.0) or 0.0,
                    fill_percentage=fill_percentage
                )

                valid_containers.append(container_option)
                logger.info(f"CONTAINER_VALIDATION: Successfully added {container.name} to valid options")

            except Exception as e:
                logger.error(f"CONTAINER_VALIDATION: Failed to process container {container.name}: {e}", exc_info=True)
                continue

        logger.info(f"CONTAINER_CONVERSION: Processed {len(valid_containers)} valid containers")
        return valid_containers

    except Exception as e:
        logger.error(f"Error getting valid containers: {e}")
        return []


def _convert_container_capacities(
    containers: List[InventoryItem],
    target_yield: float,
    yield_unit: str
) -> List[ContainerOption]:
    """
    Convert container capacities to recipe yield units and create ContainerOption objects.
    """
    conversion_engine = ConversionEngine()
    valid_options = []

    for container in containers:
        try:
            # Get container capacity info
            capacity_amount = getattr(container, 'capacity', 0)
            capacity_unit = getattr(container, 'capacity_unit', '') or getattr(container, 'unit', '')

            if not capacity_amount or not capacity_unit:
                logger.warning(f"Container {container.name} missing capacity info")
                continue

            # Convert capacity to recipe yield units
            converted_capacity = conversion_engine.convert_units(
                amount=float(capacity_amount),
                from_unit=capacity_unit,
                to_unit=yield_unit
            )

            if converted_capacity <= 0:
                continue

            # Calculate how many containers needed
            containers_needed = max(1, int(Decimal(str(target_yield / converted_capacity)).quantize(
                Decimal('1'), rounding=ROUND_UP
            )))

            # Calculate fill percentage of last container
            if containers_needed == 1:
                fill_percentage = min(100.0, (target_yield / converted_capacity) * 100)
            else:
                last_container_fill = target_yield - (converted_capacity * (containers_needed - 1))
                fill_percentage = (last_container_fill / converted_capacity) * 100

            # Create ContainerOption
            option = ContainerOption(
                container_id=container.id,
                container_name=container.name,
                capacity=converted_capacity,
                available_quantity=int(container.quantity),
                containers_needed=containers_needed,
                cost_each=getattr(container, 'cost_per_unit', 0.0) or 0.0,
                fill_percentage=fill_percentage
            )

            valid_options.append(option)

        except Exception as e:
            logger.warning(f"Failed to process container {container.name}: {e}")
            continue

    # Sort by capacity (largest first) for greedy algorithm
    valid_options.sort(key=lambda x: x.capacity, reverse=True)

    logger.info(f"CONTAINER_CONVERSION: Processed {len(valid_options)} valid containers")
    return valid_options


def _create_auto_fill_strategy(
    container_options: List[ContainerOption],
    target_yield: float
) -> Optional[ContainerStrategy]:
    """
    Implement true greedy algorithm for optimal container selection.
    Uses "making change" approach with largest containers first.
    """
    if not container_options:
        return None

    remaining_yield = target_yield
    selected_containers = []
    warnings = []

    # Greedy algorithm: use largest containers first
    for container in container_options:
        if remaining_yield <= 0:
            break

        if container.available_quantity <= 0:
            continue

        # Calculate how many of this container we can use
        containers_that_fit = int(remaining_yield / container.capacity)
        containers_available = container.available_quantity
        containers_to_use = min(containers_that_fit, containers_available)

        if containers_to_use > 0:
            # Create a copy with the quantity we're actually using
            selected_container = ContainerOption(
                container_id=container.container_id,
                container_name=container.container_name,
                capacity=container.capacity,
                available_quantity=container.available_quantity,
                containers_needed=containers_to_use,
                cost_each=container.cost_each
            )

            selected_containers.append(selected_container)
            remaining_yield -= containers_to_use * container.capacity

            logger.info(f"GREEDY_FILL: Selected {containers_to_use}x {container.container_name} "
                       f"({containers_to_use * container.capacity} units), remaining: {remaining_yield}")

    # Check if we need one more container for remaining yield
    if remaining_yield > 0 and container_options:
        # Find smallest container that can hold the remainder
        for container in sorted(container_options, key=lambda x: x.capacity):
            if container.capacity >= remaining_yield and container.available_quantity > 0:
                # Check if we already selected this container type
                existing = next((c for c in selected_containers if c.container_id == container.container_id), None)
                if existing and existing.containers_needed < container.available_quantity:
                    # Add one more of this container
                    existing.containers_needed += 1
                    remaining_yield = 0
                    warnings.append(f"Added partial fill container: {container.container_name}")
                elif not existing:
                    # Add new container for partial fill
                    partial_container = ContainerOption(
                        container_id=container.container_id,
                        container_name=container.container_name,
                        capacity=container.capacity,
                        available_quantity=container.available_quantity,
                        containers_needed=1,
                        cost_each=container.cost_each
                    )
                    selected_containers.append(partial_container)
                    remaining_yield = 0
                    warnings.append(f"Added partial fill container: {container.container_name}")
                break

    # Calculate strategy metrics
    total_capacity = sum(c.capacity * c.containers_needed for c in selected_containers)
    containment_percentage = min(100.0, (total_capacity / target_yield) * 100) if target_yield > 0 else 0

    if remaining_yield > 0:
        warnings.append(f"Unable to fully contain batch: {remaining_yield:.2f} units remaining")

    strategy = ContainerStrategy(
        selected_containers=selected_containers,
        total_capacity=total_capacity,
        containment_percentage=containment_percentage,
        warnings=warnings
    )

    logger.info(f"GREEDY_STRATEGY: {len(selected_containers)} container types selected, "
               f"{containment_percentage:.1f}% containment")

    return strategy


def _strategy_to_dict(strategy: ContainerStrategy) -> Dict[str, Any]:
    """Convert ContainerStrategy to dictionary for API response"""
    return {
        'container_selection': [
            {
                'container_id': c.container_id,
                'container_name': c.container_name,
                'capacity': c.capacity,
                'available_quantity': c.available_quantity,
                'containers_needed': c.containers_needed,
                'cost_each': c.cost_each
            }
            for c in strategy.selected_containers
        ],
        'total_capacity': strategy.total_capacity,
        'containment_percentage': strategy.containment_percentage,
        'is_complete': strategy.is_complete,
        'warnings': strategy.warnings
    }


def _container_option_to_dict(option: ContainerOption) -> Dict[str, Any]:
    """Convert ContainerOption to dictionary for API response"""
    return {
        'container_id': option.container_id,
        'container_name': option.container_name,
        'capacity': option.capacity,
        'available_quantity': option.available_quantity,
        'containers_needed': option.containers_needed,
        'cost_each': option.cost_each,
        'fill_percentage': option.fill_percentage,
        'total_capacity': option.total_capacity
    }


def _debug_container_search(organization_id: int, yield_unit: str) -> None:
    """Debug function to help troubleshoot container search issues"""
    try:
        logger.info(f"CONTAINER_DEBUG: Debugging container search for org {organization_id}, yield unit {yield_unit}")

        # Check if container category exists
        container_category = IngredientCategory.query.filter_by(
            name='Container',
            organization_id=organization_id
        ).first()

        if not container_category:
            logger.warning(f"CONTAINER_DEBUG: No 'Container' category found for organization {organization_id}")

            # Check what categories do exist
            categories = IngredientCategory.query.filter_by(organization_id=organization_id).all()
            logger.info(f"CONTAINER_DEBUG: Available categories: {[c.name for c in categories]}")
            return

        logger.info(f"CONTAINER_DEBUG: Container category found: ID {container_category.id}")

        # Check containers in the category
        containers = InventoryItem.query.filter_by(
            organization_id=organization_id,
            category_id=container_category.id
        ).all()

        logger.info(f"CONTAINER_DEBUG: Found {len(containers)} containers in category")

        for container in containers:
            capacity = getattr(container, 'capacity', None)
            capacity_unit = getattr(container, 'capacity_unit', None)
            quantity = getattr(container, 'quantity', 0)

            logger.info(f"CONTAINER_DEBUG: {container.name} - capacity: {capacity} {capacity_unit}, quantity: {quantity}")

            if not capacity or not capacity_unit:
                logger.warning(f"CONTAINER_DEBUG: {container.name} missing capacity info")

    except Exception as e:
        logger.error(f"CONTAINER_DEBUG: Error in debug function: {e}", exc_info=True)