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
    try:
        # Calculate target yield
        target_yield = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'count'

        logger.info(f"CONTAINER_ANALYSIS: Recipe {recipe.name}, scale {scale}, target {target_yield} {yield_unit}")

        # Get all valid containers
        container_options = _get_all_valid_containers(recipe, organization_id, target_yield, yield_unit)

        if not container_options:
            logger.warning(f"CONTAINER_ANALYSIS: No valid containers found for recipe {recipe.id}")
            return None, []

        # Create auto-fill strategy using greedy algorithm
        strategy = _create_auto_fill_strategy(container_options, target_yield)

        # Convert to API format
        if api_format:
            strategy_dict = _strategy_to_dict(strategy) if strategy else None
            options_list = [_container_option_to_dict(opt) for opt in container_options]
            return strategy_dict, options_list
        else:
            return strategy, container_options

    except Exception as e:
        logger.error(f"Error in container analysis: {e}")
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
                # Get container capacity using the correct field names
                capacity_value = getattr(container, 'capacity', None)
                capacity_unit = getattr(container, 'capacity_unit', None)

                if not capacity_value or not capacity_unit:
                    logger.warning(f"Container {container.name} missing capacity/storage amount or unit")
                    continue

                # Convert container capacity to recipe yield unit
                conversion_result = conversion_engine.convert(
                    amount=float(capacity_value),
                    from_unit=capacity_unit,
                    to_unit=yield_unit,
                    organization_id=organization_id
                )

                # Handle conversion result properly - it might be a dict with error info
                if isinstance(conversion_result, dict):
                    if conversion_result.get('success') and 'converted_amount' in conversion_result:
                        converted_capacity = float(conversion_result['converted_amount'])
                    else:
                        logger.warning(f"Conversion failed for container {container.name}: {conversion_result.get('error', 'Unknown error')}")
                        continue
                elif isinstance(conversion_result, (int, float)):
                    converted_capacity = float(conversion_result)
                else:
                    logger.warning(f"Invalid conversion result for container {container.name}: {conversion_result}")
                    continue

                # Skip if conversion failed or invalid
                if not converted_capacity or converted_capacity <= 0:
                    logger.warning(f"Invalid converted capacity for container {container.name}: {converted_capacity}")
                    continue

                # Calculate containers needed
                containers_needed = max(1, int((target_yield / converted_capacity) + 0.5))  # Round up

                container_option = ContainerOption(
                    container_id=container.id,
                    container_name=container.name,
                    capacity=converted_capacity,
                    capacity_unit=yield_unit,
                    containers_needed=containers_needed,
                    total_capacity=converted_capacity * containers_needed,
                    fill_percentage=(target_yield / (converted_capacity * containers_needed)) * 100
                )

                valid_containers.append(container_option)

            except Exception as e:
                logger.warning(f"Failed to process container {container.name}: {e}")
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