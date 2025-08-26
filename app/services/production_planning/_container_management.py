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
    organization_id: Optional[int] = None
) -> Tuple[Optional[ContainerStrategy], List[Dict[str, Any]]]:
    """
    Analyze container options for a recipe at given scale.

    Returns:
        Tuple of (container_strategy, container_options_list)
    """
    try:
        # Get yield requirements
        total_yield = (recipe.predicted_yield or 0) * scale
        if total_yield <= 0:
            logger.warning(f"No yield calculated for recipe {recipe.id} at scale {scale}")
            return None, []

        # Get allowed containers for this recipe
        allowed_containers = getattr(recipe, 'allowed_containers', [])
        if not allowed_containers:
            logger.info(f"No allowed containers specified for recipe {recipe.id}")
            return None, []

        # Use USCS to check container availability
        uscs = UniversalStockCheckService()
        container_options = []

        for container_id in allowed_containers:
            try:
                # Check container stock via USCS
                result = uscs.check_single_item(
                    item_id=container_id,
                    quantity_needed=1.0,  # We'll calculate needed quantity separately
                    unit='count',
                    category=InventoryCategory.CONTAINER
                )

                if result.status != StockStatus.ERROR:
                    # Get container details
                    container = InventoryItem.query.get(container_id)
                    if container and hasattr(container, 'capacity') and container.capacity:

                        # Calculate containers needed
                        container_capacity = container.capacity
                        containers_needed = int((total_yield / container_capacity) + 0.99)  # Round up

                        # Check if we have enough containers
                        available_qty = result.available_quantity

                        container_option = {
                            'id': container_id,
                            'name': container.name,
                            'capacity': container_capacity,
                            'available_quantity': int(available_qty),
                            'quantity': containers_needed,
                            'stock_qty': int(available_qty),
                            'unit': getattr(container, 'unit', 'count')
                        }

                        container_options.append(container_option)

            except Exception as e:
                logger.error(f"Error checking container {container_id}: {e}")
                continue

        if not container_options:
            return None, []

        # Create container strategy
        # For now, use the first available container that has enough stock
        selected_container = None
        for option in container_options:
            if option['available_quantity'] >= option['quantity']:
                selected_container = option
                break

        if not selected_container:
            # No single container type has enough stock
            return None, container_options

        # Create strategy
        container_strategy = ContainerStrategy(
            selected_containers=[ContainerOption(
                container_id=selected_container['id'],
                container_name=selected_container['name'],
                capacity=selected_container['capacity'],
                available_quantity=selected_container['available_quantity'],
                containers_needed=selected_container['quantity'],
                cost_each=0.0  # TODO: Add cost calculation
            )],
            total_capacity=selected_container['capacity'] * selected_container['quantity'],
            containment_percentage=100.0,  # Full containment achieved
            fill_strategy=ContainerFillStrategy(
                selected_containers=[selected_container],
                total_capacity=selected_container['capacity'] * selected_container['quantity'],
                containment_percentage=100.0,
                strategy_type="auto"
            )
        )

        return container_strategy, container_options

    except Exception as e:
        logger.error(f"Error in analyze_container_options: {e}")
        return None, []


def get_container_plan_for_api(recipe_id: int, scale: float) -> Dict[str, Any]:
    """
    API endpoint for container planning - returns JSON-ready data.
    """
    try:
        from ...models import Recipe

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        org_id = current_user.organization_id if current_user.is_authenticated else None

        strategy, options = analyze_container_options(recipe, scale, None, org_id)

        if not strategy and not options:
            return {
                'success': False,
                'error': 'No suitable containers found for this recipe'
            }

        # Calculate total capacity and containment
        total_yield = (recipe.predicted_yield or 0) * scale

        if strategy:
            return {
                'success': True,
                'container_selection': strategy.fill_strategy.selected_containers,
                'total_capacity': strategy.total_capacity,
                'containment_percentage': strategy.containment_percentage
            }
        else:
            return {
                'success': False,
                'error': 'Insufficient container stock',
                'available_options': options,
                'required_yield': total_yield
            }

    except Exception as e:
        logger.error(f"Error in get_container_plan_for_api: {e}")
        return {'success': False, 'error': str(e)}