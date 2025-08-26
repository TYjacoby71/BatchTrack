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

        # Analyze containers directly (no USCS needed)
        from ..unit_conversion import ConversionEngine
        container_options = []

        for container in all_containers:
            logger.info(f"CONTAINER_ANALYSIS: Analyzing container {container.name}...")

            # Skip containers without storage capacity
            storage_capacity = getattr(container, 'storage_amount', 0)
            storage_unit = getattr(container, 'storage_unit', 'ml')
            
            if not storage_capacity or storage_capacity <= 0:
                logger.info(f"CONTAINER_ANALYSIS: Skipping {container.name} - no storage capacity")
                continue

            try:
                # Convert container storage capacity to recipe yield unit
                if yield_unit != storage_unit:
                    conversion_result = ConversionEngine.convert_units(
                        storage_capacity,
                        storage_unit,
                        yield_unit,
                        ingredient_id=None  # Containers don't need ingredient context
                    )
                    
                    if isinstance(conversion_result, dict):
                        capacity_in_recipe_units = conversion_result['converted_value']
                    else:
                        capacity_in_recipe_units = float(conversion_result)
                else:
                    capacity_in_recipe_units = storage_capacity

                # Calculate fill analysis
                containers_needed = max(1, int(total_yield / capacity_in_recipe_units)) if capacity_in_recipe_units > 0 else 1
                total_capacity_needed = containers_needed * capacity_in_recipe_units
                fill_percentage = (total_yield / total_capacity_needed * 100) if total_capacity_needed > 0 else 0
                waste_percentage = max(0, 100 - fill_percentage)

                logger.info(f"CONTAINER_ANALYSIS: {container.name} - Need {containers_needed} containers, Fill: {fill_percentage:.1f}%")

                container_option = ContainerOption(
                    id=container.id,
                    name=container.name,
                    capacity=storage_capacity,
                    unit=storage_unit,
                    available_quantity=int(container.quantity),
                    quantity=containers_needed,
                    stock_qty=int(container.quantity),  # For JS compatibility
                    fill_percentage=fill_percentage,
                    waste_percentage=waste_percentage,
                    total_capacity=total_capacity_needed,
                    cost_per_unit=getattr(container, 'cost_per_unit', 0) or 0
                )

                container_options.append(container_option)
                logger.info(f"CONTAINER_ANALYSIS: Added container option: {container_option.name}")

            except Exception as e:
                logger.error(f"CONTAINER_ANALYSIS: Error analyzing container {container.name}: {e}")

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