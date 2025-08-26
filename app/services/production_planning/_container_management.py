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
    Only considers containers specifically allowed by the recipe.

    Returns:
        Tuple of (container_strategy, container_options_list)
    """
    try:
        # Get yield requirements
        total_yield = (recipe.predicted_yield or 0) * scale
        if total_yield <= 0:
            logger.warning(f"No yield calculated for recipe {recipe.id} at scale {scale}")
            return None, []

        # Get ONLY allowed containers for this recipe - no fallback to all containers
        allowed_containers = []
        
        # Check if recipe has allowed_containers relationship or field
        if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
            allowed_containers = [c.id if hasattr(c, 'id') else c for c in recipe.allowed_containers]
        elif hasattr(recipe, 'container_ids') and recipe.container_ids:
            allowed_containers = recipe.container_ids
        
        if not allowed_containers:
            logger.warning(f"Recipe {recipe.id} has no allowed containers defined - this recipe needs containers assigned to it")
            return None, []

        logger.info(f"Recipe {recipe.id} has {len(allowed_containers)} allowed containers: {allowed_containers}")

        # Get container details and filter for proper storage capacity
        container_options = []
        org_id = organization_id or (current_user.organization_id if current_user.is_authenticated else None)

        for container_id in allowed_containers:
            try:
                # Get container details directly
                container = InventoryItem.query.filter_by(
                    id=container_id,
                    organization_id=org_id
                ).first()

                if not container:
                    logger.warning(f"Container {container_id} not found in organization {org_id}")
                    continue

                # REQUIRE proper storage capacity - skip containers without it
                storage_capacity = getattr(container, 'storage_amount', None)
                storage_unit = getattr(container, 'storage_unit', None)
                
                if not storage_capacity or not storage_unit:
                    logger.warning(f"Container {container.name} (ID: {container_id}) has no storage capacity - skipping")
                    continue

                # Check if we have stock
                available_qty = container.quantity or 0
                if available_qty <= 0:
                    logger.warning(f"Container {container.name} has no stock - skipping")
                    continue

                # Convert storage capacity to recipe yield unit if needed
                container_capacity_in_yield_units = storage_capacity
                if storage_unit != recipe.predicted_yield_unit:
                    # TODO: Add unit conversion here if needed
                    # For now, assume they match or use storage_capacity as-is
                    pass

                # Calculate containers needed
                containers_needed = max(1, int((total_yield / container_capacity_in_yield_units) + 0.99))

                container_option = {
                    'id': container_id,
                    'name': container.name,
                    'capacity': storage_capacity,
                    'unit': storage_unit,
                    'available_quantity': int(available_qty),
                    'quantity': containers_needed,
                    'stock_qty': int(available_qty)
                }

                container_options.append(container_option)
                logger.info(f"Added container option: {container.name} - capacity: {storage_capacity} {storage_unit}, need: {containers_needed}")

            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")
                continue

        if not container_options:
            logger.warning(f"No valid containers found for recipe {recipe.id}")
            return None, []

        # Create container strategy - use the first container that has enough stock
        selected_container = None
        for option in container_options:
            if option['available_quantity'] >= option['quantity']:
                selected_container = option
                break

        if not selected_container:
            logger.warning(f"No containers have sufficient stock for recipe {recipe.id}")
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

        logger.info(f"Created container strategy for recipe {recipe.id} using {selected_container['name']}")
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
                'error': 'No suitable containers found for this recipe. Please check that containers are assigned to this recipe and have proper storage capacity.'
            }

        if strategy:
            # Format the response to match frontend expectations
            container_selection = []
            for opt in strategy.selected_containers:
                container_selection.append({
                    'id': opt.container_id,
                    'name': opt.container_name,
                    'capacity': opt.capacity,
                    'unit': getattr(opt, 'storage_unit', 'ml'),
                    'quantity': opt.containers_needed,
                    'stock_qty': opt.available_quantity,
                    'available_quantity': opt.available_quantity
                })

            return {
                'success': True,
                'container_selection': container_selection,
                'total_capacity': strategy.total_capacity,
                'containment_percentage': strategy.containment_percentage
            }
        else:
            return {
                'success': False,
                'error': 'Insufficient container stock for required yield',
                'available_options': options,
                'required_yield': (recipe.predicted_yield or 0) * scale
            }

    except Exception as e:
        logger.error(f"Error in get_container_plan_for_api: {e}")
        return {'success': False, 'error': str(e)}