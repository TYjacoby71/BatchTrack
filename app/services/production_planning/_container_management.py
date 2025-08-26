"""
Container Management for Production Planning

Handles container selection, optimization, and fill strategies for production batches.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ...models import Recipe, InventoryItem
from flask_login import current_user
from ..stock_check import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory
from .types import ContainerStrategy, ContainerOption, ContainerFillStrategy


logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int],
    organization_id: int
) -> Tuple[Optional[ContainerStrategy], List[ContainerOption]]:
    """
    Analyze all container options for a recipe using USCS bulk query with recipe scoping.

    Returns (selected_strategy, all_options)
    """
    try:
        logger.info(f"CONTAINER_ANALYSIS: Analyzing containers for recipe {recipe.id} using USCS bulk query")

        # Calculate fill requirements
        yield_amount = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'

        logger.info(f"CONTAINER_ANALYSIS: Recipe yield {yield_amount} {yield_unit}")

        # Get allowed containers for this recipe
        allowed_container_ids = _get_recipe_allowed_containers(recipe)

        if not allowed_container_ids:
            logger.warning("CONTAINER_ANALYSIS: No allowed containers found for recipe")
            return None, []

        # Use USCS single item checks for each allowed container
        uscs = UniversalStockCheckService()
        container_results = []

        for container_id in allowed_container_ids:
            result = uscs.check_single_item(
                item_id=container_id,
                quantity_needed=1,  # Check for at least 1 container
                unit="count",
                category=InventoryCategory.CONTAINER
            )
            container_results.append(result)

        logger.info(f"CONTAINER_ANALYSIS: USCS returned {len(container_results)} container results")

        if not container_results:
            logger.warning("CONTAINER_ANALYSIS: No containers found by USCS")
            return None, []

        # Convert USCS results to ContainerOptions
        analyzed_options = []
        for result in container_results:
            if result.status in ['available', 'sufficient', 'ok'] and result.conversion_details:
                storage_capacity = result.conversion_details.get('storage_capacity', 0)
                storage_unit = result.conversion_details.get('storage_unit', 'ml')
                yield_in_storage_units = result.conversion_details.get('yield_in_storage_units', 0)
                containers_needed = result.needed_quantity

                # Calculate fill percentage
                total_capacity = storage_capacity * containers_needed
                fill_percentage = (yield_in_storage_units / total_capacity * 100) if total_capacity > 0 else 0

                option = ContainerOption(
                    container_id=result.item_id,
                    container_name=result.item_name,
                    storage_capacity=storage_capacity,
                    storage_unit=storage_unit,
                    available_quantity=result.available_quantity,
                    cost_each=result.conversion_details.get('cost_per_unit', 0) or 0,
                    fill_percentage=fill_percentage,
                    containers_needed=int(containers_needed)
                )

                analyzed_options.append(option)
                logger.info(f"CONTAINER_ANALYSIS: {result.item_name} - needs {containers_needed} containers, fill: {fill_percentage:.1f}%")

        if not analyzed_options:
            logger.warning("No suitable container options found after USCS bulk analysis")
            return None, []

        # Select best strategy
        if preferred_container_id:
            strategy = _create_user_specified_strategy(analyzed_options, preferred_container_id)
        else:
            strategy = _select_optimal_strategy(analyzed_options)

        logger.info(f"CONTAINER_ANALYSIS: Selected strategy {strategy.strategy_type.value}")
        return strategy, analyzed_options

    except Exception as e:
        logger.error(f"Error analyzing container options: {e}")
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