"""
Production Planning Operations - DEPRECATED

This module now delegates to the dedicated Production Planning Service Package.
The logic has been moved to app/services/production_planning/ for better organization.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def plan_production(recipe_id: int, scale: float = 1.0,
                   container_id: int = None, check_containers: bool = False) -> Dict[str, Any]:
    """
    Plan production for a recipe - DELEGATES to Production Planning Service.
    
    This function is kept for backwards compatibility but now delegates
    to the dedicated production planning service package.
    """
    try:
        # Delegate to the new production planning service
        from ...services.production_planning import plan_production_comprehensive
        
        return plan_production_comprehensive(
            recipe_id=recipe_id,
            scale=scale,
            preferred_container_id=container_id,
            include_container_analysis=check_containers
        )
        
    except Exception as e:
        logger.error(f"Error delegating to production planning service: {e}")
        return {'success': False, 'error': str(e)}


def calculate_recipe_requirements(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate ingredient requirements - DELEGATES to Production Planning Service.
    """
    try:
        from ...services.production_planning import calculate_production_requirements
        return calculate_production_requirements(recipe_id, scale)
        
    except Exception as e:
        logger.error(f"Error delegating recipe requirements calculation: {e}")
        return {'success': False, 'error': str(e)}


def check_ingredient_availability(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check ingredient availability - DELEGATES to Production Planning Service.
    """
    try:
        from ...services.production_planning import validate_ingredient_availability
        return validate_ingredient_availability(recipe_id, scale)
        
    except Exception as e:
        logger.error(f"Error delegating ingredient availability check: {e}")
        return {'success': False, 'error': str(e)}


def calculate_production_cost(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate the cost of producing a recipe at given scale.

    Args:
        recipe_id: Recipe to calculate cost for
        scale: Scaling factor

    Returns:
        Dict with cost information
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        total_cost = Decimal('0.00')
        ingredient_costs = []

        for recipe_ingredient in recipe.recipe_ingredients:
            cost_per_unit = getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0
            scaled_quantity = recipe_ingredient.quantity * scale
            ingredient_cost = Decimal(str(cost_per_unit)) * Decimal(str(scaled_quantity))

            total_cost += ingredient_cost

            ingredient_costs.append({
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'quantity': scaled_quantity,
                'unit': recipe_ingredient.unit,
                'cost_per_unit': float(cost_per_unit),
                'total_cost': float(ingredient_cost)
            })

        # Calculate cost per unit if yield is known
        cost_per_unit = 0
        if recipe.predicted_yield and recipe.predicted_yield > 0:
            yield_amount = recipe.predicted_yield * scale
            cost_per_unit = float(total_cost) / yield_amount

        return {
            'total_cost': float(total_cost),
            'cost_per_unit': cost_per_unit,
            'yield_amount': (recipe.predicted_yield or 0) * scale,
            'yield_unit': recipe.predicted_yield_unit or 'count',
            'ingredient_costs': ingredient_costs
        }

    except Exception as e:
        logger.error(f"Error calculating production cost for recipe {recipe_id}: {e}")
        return {'error': str(e)}


def _build_recipe_requests(recipe, scale: float, check_containers: bool = False) -> List[StockCheckRequest]:
    """Build stock check requests from recipe ingredients and optionally containers"""
    requests = []

    # Add ingredient requests
    for recipe_ingredient in recipe.recipe_ingredients:
        requests.append(StockCheckRequest(
            item_id=recipe_ingredient.inventory_item_id,
            quantity_needed=recipe_ingredient.quantity * scale,
            unit=recipe_ingredient.unit,
            category=InventoryCategory.INGREDIENT,
            organization_id=current_user.organization_id if current_user.is_authenticated else None,
            scale_factor=scale
        ))

    # Add container requests if requested
    if check_containers:
        # Get containers allowed for this recipe or all available containers
        from ...models import InventoryItem
        from flask_login import current_user

        # Check if recipe has specific allowed containers
        if recipe.allowed_containers:
            # Filter to only allowed containers
            containers = InventoryItem.query.filter(
                InventoryItem.id.in_(recipe.allowed_containers),
                InventoryItem.type == 'container',
                InventoryItem.organization_id == (current_user.organization_id if current_user.is_authenticated else None)
            ).all()
        else:
            # Get all available containers for this organization
            containers = InventoryItem.query.filter_by(
                type='container',
                organization_id=current_user.organization_id if current_user.is_authenticated else None
            ).all()

        # Check if no containers are specified and the toggle is selected
        if check_containers and not recipe.allowed_containers and not containers:
            logger.warning(f"User has not specified any allowable containers for recipe {recipe.id}, but container toggle is selected.")
            # Optionally, you could raise an alert here or return a specific status

        yield_amount = recipe.predicted_yield * scale if recipe.predicted_yield else 1.0

        for container in containers:
            # Only include containers that have stock
            if hasattr(container, 'quantity') and container.quantity > 0:
                requests.append(StockCheckRequest(
                    item_id=container.id,
                    quantity_needed=1,  # Check for at least 1 container
                    unit="count",
                    category=InventoryCategory.CONTAINER,
                    organization_id=current_user.organization_id if current_user.is_authenticated else None,
                    scale_factor=scale
                ))

    return requests


def _process_stock_results(stock_results: List) -> List[Dict[str, Any]]:
    """Process stock check results into consistent format"""
    processed = []

    for result in stock_results:
        # Handle both StockCheckResult objects and dicts
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        else:
            result_dict = result

        base_result = {
            'item_id': result_dict.get('item_id'),
            'item_name': result_dict.get('item_name', 'Unknown'),
            'name': result_dict.get('item_name', 'Unknown'),  # Backwards compatibility
            'needed_quantity': result_dict.get('needed_quantity', 0),
            'needed': result_dict.get('needed_quantity', 0),  # Backwards compatibility
            'needed_unit': result_dict.get('needed_unit', ''),
            'available_quantity': result_dict.get('available_quantity', 0),
            'available': result_dict.get('available_quantity', 0),  # Backwards compatibility
            'available_unit': result_dict.get('available_unit', ''),
            'unit': result_dict.get('needed_unit', ''),  # Backwards compatibility
            'status': result_dict.get('status', 'UNKNOWN'),
            'category': result_dict.get('category', 'ingredient'),
            'type': result_dict.get('category', 'ingredient')  # Backwards compatibility
        }

        # Add container-specific fields if this is a container
        if result_dict.get('category') == 'container':
            conversion_details = result_dict.get('conversion_details', {})
            base_result.update({
                'storage_amount': conversion_details.get('storage_capacity', 0),
                'storage_unit': conversion_details.get('storage_unit', 'ml'),
                'stock_qty': result_dict.get('available_quantity', 0)
            })

        processed.append(base_result)

    return processed