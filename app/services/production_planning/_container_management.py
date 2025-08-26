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
from .types import ContainerOption, ContainerStrategy, ContainerFillStrategy


logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int],
    organization_id: int
) -> Tuple[Optional[ContainerStrategy], List[ContainerOption]]:
    """
    Analyze all container options for a recipe using USCS container handler.

    Returns (selected_strategy, all_options)
    """
    try:
        logger.info(f"CONTAINER_ANALYSIS: Analyzing containers for recipe {recipe.id} using USCS")

        # Get available containers
        container_items = _get_available_containers(recipe, organization_id)

        if not container_items:
            logger.warning(f"No containers available for recipe {recipe.id}")
            return None, []

        # Calculate fill requirements
        yield_amount = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'

        logger.info(f"CONTAINER_ANALYSIS: Recipe yield {yield_amount} {yield_unit}")

        # Use USCS to analyze each container option with proper unit conversion
        from ..stock_check import UniversalStockCheckService
        from ..stock_check.types import InventoryCategory

        uscs = UniversalStockCheckService()
        analyzed_options = []

        for container in container_items:
            logger.info(f"CONTAINER_ANALYSIS: Checking container {container.name} via USCS")

            # Use USCS to check container capacity vs yield requirements
            result = uscs.check_single_item(
                item_id=container.id,
                quantity_needed=yield_amount,  # Recipe yield amount
                unit=yield_unit,  # Recipe yield unit
                category=InventoryCategory.CONTAINER
            )

            # Convert USCS result to ContainerOption
            if result.conversion_details:
                storage_capacity = result.conversion_details.get('storage_capacity', 0)
                storage_unit = result.conversion_details.get('storage_unit', 'ml')
                yield_in_storage_units = result.conversion_details.get('yield_in_storage_units', 0)
                containers_needed = result.needed_quantity  # USCS calculates containers needed

                # Calculate fill percentage
                total_capacity = storage_capacity * containers_needed
                fill_percentage = (yield_in_storage_units / total_capacity * 100) if total_capacity > 0 else 0

                option = ContainerOption(
                    container_id=container.id,
                    container_name=container.name,
                    storage_capacity=storage_capacity,
                    storage_unit=storage_unit,
                    available_quantity=result.available_quantity,
                    cost_each=getattr(container, 'cost_per_unit', 0) or 0,
                    fill_percentage=fill_percentage,
                    containers_needed=int(containers_needed)
                )

                analyzed_options.append(option)
                logger.info(f"CONTAINER_ANALYSIS: {container.name} - needs {containers_needed} containers, fill: {fill_percentage:.1f}%")
            else:
                logger.warning(f"CONTAINER_ANALYSIS: No conversion details for {container.name}")

        if not analyzed_options:
            logger.warning("No suitable container options found after USCS analysis")
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


def _get_available_containers(recipe: Recipe, organization_id: int) -> List[InventoryItem]:
    """Get containers available for this recipe"""
    try:
        # Check if recipe has specific allowed containers
        if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
            containers = InventoryItem.query.filter(
                InventoryItem.id.in_(recipe.allowed_containers),
                InventoryItem.type == 'container',
                InventoryItem.organization_id == organization_id
            ).all()
        else:
            # Get all available containers for this organization
            containers = InventoryItem.query.filter_by(
                type='container',
                organization_id=organization_id
            ).all()

        # Filter to only containers with stock
        available_containers = [c for c in containers if hasattr(c, 'quantity') and (c.quantity or 0) > 0]

        logger.info(f"Found {len(available_containers)} available containers")
        return available_containers

    except Exception as e:
        logger.error(f"Error getting available containers: {e}")
        return []





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
        average_fill_percentage=selected_option.fill_percentage,
        waste_percentage=waste_percentage
    )





