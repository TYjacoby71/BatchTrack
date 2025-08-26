"""
Container Management for Production Planning

Handles container selection, optimization, and fill strategies for production batches.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ...models import Recipe, InventoryItem
from flask_login import current_user
from ..stock_check import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory, StockStatus
from .types import ContainerStrategy, ContainerOption, ContainerFillStrategy


logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int] = None,
    organization_id: int = None
) -> Tuple[Optional[ContainerStrategy], List[ContainerOption]]:
    """
    Analyze available containers and determine the best strategy for production.

    Returns:
        Tuple of (container_strategy, container_options_list)
    """
    logger.info(f"CONTAINER_ANALYSIS: Starting analysis for recipe {recipe.id}, scale {scale}, org {organization_id}")

    # Calculate total recipe yield in the recipe's yield unit
    total_yield = (recipe.predicted_yield or 0) * scale
    yield_unit = recipe.predicted_yield_unit or 'ml'

    logger.info(f"CONTAINER_ANALYSIS: Recipe yield {total_yield} {yield_unit}")

    if total_yield <= 0:
        logger.warning(f"CONTAINER_ANALYSIS: Invalid recipe yield {total_yield}")
        return None, []

    try:
        # Get all containers for this organization
        from ...models import InventoryItem
        all_containers = InventoryItem.query.filter_by(
            type='container',
            organization_id=organization_id
        ).filter(InventoryItem.quantity > 0).all()

        logger.info(f"CONTAINER_ANALYSIS: Found {len(all_containers)} containers in database")
        for container in all_containers:
            logger.info(f"CONTAINER_ANALYSIS: - DB Container: {container.name} (ID: {container.id})")
            logger.info(f"CONTAINER_ANALYSIS: - Quantity: {container.quantity}")
            logger.info(f"CONTAINER_ANALYSIS: - Storage: {getattr(container, 'storage_amount', 'None')} {getattr(container, 'storage_unit', 'None')}")

        # Use USCS to check each container
        uscs = UniversalStockCheckService()
        container_results = []

        for container in all_containers:
            logger.info(f"CONTAINER_ANALYSIS: Checking container {container.name} via USCS...")

            try:
                # Use USCS to check this container
                result = uscs.check_single_item(
                    item_id=container.id,
                    quantity_needed=total_yield, 
                    unit=yield_unit,
                    category=InventoryCategory.CONTAINER
                )

                logger.info(f"CONTAINER_ANALYSIS: USCS result for {container.name}:")
                logger.info(f"CONTAINER_ANALYSIS: - Status: {result.status}")
                logger.info(f"CONTAINER_ANALYSIS: - Item ID: {result.item_id}")
                logger.info(f"CONTAINER_ANALYSIS: - Available quantity: {result.available_quantity}")
                logger.info(f"CONTAINER_ANALYSIS: - Error message: {getattr(result, 'error_message', 'None')}")
                logger.info(f"CONTAINER_ANALYSIS: - Conversion details: {getattr(result, 'conversion_details', 'None')}")

                container_results.append(result)

            except Exception as e:
                logger.error(f"CONTAINER_ANALYSIS: Error checking container {container.name}: {e}")

        logger.info(f"CONTAINER_ANALYSIS: USCS returned {len(container_results)} container results")

        container_options = []

        for result in container_results:
            logger.info(f"CONTAINER_ANALYSIS: Processing result for {result.item_name}")
            logger.info(f"CONTAINER_ANALYSIS: - Status: {result.status} (type: {type(result.status)})")
            logger.info(f"CONTAINER_ANALYSIS: - Status value: {result.status.value if hasattr(result.status, 'value') else 'no value'}")
            logger.info(f"CONTAINER_ANALYSIS: - Has conversion_details: {hasattr(result, 'conversion_details') and result.conversion_details is not None}")

            # Check for StockStatus.OK (our new status for available containers)
            if result.status == StockStatus.OK and hasattr(result, 'conversion_details') and result.conversion_details:
                logger.info(f"CONTAINER_ANALYSIS: Container {result.item_name} passed initial checks")

                conversion_details = result.conversion_details
                logger.info(f"CONTAINER_ANALYSIS: Conversion details: {conversion_details}")

                # Extract container properties from conversion details
                capacity = conversion_details.get('storage_capacity', 0)
                capacity_unit = conversion_details.get('storage_unit', 'ml')
                capacity_in_recipe_units = conversion_details.get('storage_capacity_in_recipe_units', capacity)

                logger.info(f"CONTAINER_ANALYSIS: Capacity: {capacity} {capacity_unit}, Recipe units: {capacity_in_recipe_units}")

                # Calculate fill analysis
                containers_needed = max(1, int(total_yield / capacity_in_recipe_units)) if capacity_in_recipe_units > 0 else 1
                total_capacity_needed = containers_needed * capacity_in_recipe_units
                fill_percentage = (total_yield / total_capacity_needed * 100) if total_capacity_needed > 0 else 0
                waste_percentage = max(0, 100 - fill_percentage)

                logger.info(f"CONTAINER_ANALYSIS: Calculated - Containers needed: {containers_needed}, Fill %: {fill_percentage:.1f}")

                container_option = ContainerOption(
                    id=result.item_id,
                    name=result.item_name,
                    capacity=capacity,
                    unit=capacity_unit,
                    available_quantity=int(result.available_quantity),
                    quantity=containers_needed,
                    stock_qty=int(result.available_quantity),  # For JS compatibility
                    fill_percentage=fill_percentage,
                    waste_percentage=waste_percentage,
                    total_capacity=total_capacity_needed,
                    cost_per_unit=0  # TODO: Get from inventory item
                )

                container_options.append(container_option)
                logger.info(f"CONTAINER_ANALYSIS: Added container option: {container_option.name}")
            else:
                logger.warning(f"CONTAINER_ANALYSIS: Skipping {result.item_name}")
                logger.warning(f"CONTAINER_ANALYSIS: - Status: {result.status}")
                logger.warning(f"CONTAINER_ANALYSIS: - Has conversion details: {hasattr(result, 'conversion_details') and result.conversion_details is not None}")
                logger.warning(f"CONTAINER_ANALYSIS: - Error: {getattr(result, 'error_message', 'No error message')}")

        logger.info(f"CONTAINER_ANALYSIS: Final container options count: {len(container_options)}")

        if not container_options:
            logger.warning(f"CONTAINER_ANALYSIS: No suitable containers found after processing {len(container_results)} results")
            return None, []

        # Create container strategy using the best option
        best_option = min(container_options, key=lambda x: x.waste_percentage)

        strategy = ContainerStrategy(
            selected_containers=[best_option],
            total_containers_needed=best_option.quantity,
            total_capacity=best_option.total_capacity,
            average_fill_percentage=best_option.fill_percentage,
            waste_percentage=best_option.waste_percentage,
            estimated_cost=0,  # TODO: Calculate cost
            fill_strategy=ContainerFillStrategy.MINIMIZE_WASTE
        )

        logger.info(f"CONTAINER_ANALYSIS: Strategy created with {len(strategy.selected_containers)} containers")
        return strategy, container_options

    except Exception as e:
        logger.error(f"CONTAINER_ANALYSIS: Exception in analyze_container_options: {e}")
        import traceback
        logger.error(f"CONTAINER_ANALYSIS: Traceback: {traceback.format_exc()}")
        return None, []


def _get_recipe_allowed_containers(recipe: Recipe) -> Optional[List[int]]:
    """Get recipe-specific container constraints for USCS scoping"""
    try:
        if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
            return recipe.allowed_containers
        return None  # No scoping - allow all containers
    except Exception as e:
        logger.error(f"Error getting recipe container constraints: {e}")
        return None





def _select_optimal_strategy(options: List[ContainerOption]) -> ContainerStrategy:
    """Select the optimal container strategy from available options"""

    # Sort by efficiency (fill percentage) and then by total cost
    viable_options = [opt for opt in options if opt.available_quantity >= opt.containers_needed]

    if not viable_options:
        # No perfect options, find best available
        viable_options = sorted(options, key=lambda x: (x.available_quantity, -x.fill_percentage))
        viable_options = viable_options[:1] if viable_options else []

    if not viable_options:
        raise ValueError("No viable container options")

    # Select strategy based on options
    if len(viable_options) == 1:
        selected = viable_options[0]
        strategy_type = ContainerFillStrategy.SINGLE_LARGE
    else:
        # Select highest efficiency option
        selected = max(viable_options, key=lambda x: x.fill_percentage)
        strategy_type = ContainerFillStrategy.SINGLE_LARGE

    total_cost = selected.cost_each * selected.containers_needed
    waste_percentage = max(0, 100 - selected.fill_percentage)

    return ContainerStrategy(
        strategy_type=strategy_type,
        selected_containers=[selected],
        total_containers_needed=selected.containers_needed,
        total_container_cost=total_cost,
        average_fill_percentage=selected.fill_percentage,
        waste_percentage=waste_percentage
    )


def _create_user_specified_strategy(options: List[ContainerOption], container_id: int) -> Optional[ContainerStrategy]:
    """Create strategy for user-specified container"""

    selected_option = next((opt for opt in options if opt.container_id == container_id), None)

    if not selected_option:
        # Fall back to optimal strategy
        return _select_optimal_strategy(options)

    total_cost = selected_option.cost_each * selected_option.containers_needed
    waste_percentage = max(0, 100 - selected_option.fill_percentage)

    return ContainerStrategy(
        strategy_type=ContainerFillStrategy.USER_SPECIFIED,
        selected_containers=[selected_option],
        total_containers_needed=selected_option.containers_needed,
        total_container_cost=total_cost,
        average_fill_percentage=selected.fill_percentage,
        waste_percentage=waste_percentage
    )