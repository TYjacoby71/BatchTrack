
"""
Production Planning Operations

Handles planning production batches from recipes, checking stock availability,
and calculating requirements using the UniversalStockCheckService.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal

from ...models import Recipe, RecipeIngredient, InventoryItem
from ...services.stock_check import UniversalStockCheckService
from ...services.stock_check.types import StockCheckRequest, InventoryCategory

logger = logging.getLogger(__name__)


def plan_production(recipe_id: int, scale: float = 1.0,
                   container_id: int = None, check_containers: bool = False) -> Dict[str, Any]:
    """
    Plan production for a recipe with comprehensive stock checking.

    Args:
        recipe_id: Recipe to plan
        scale: Scaling factor for recipe
        container_id: Optional container for batch
        check_containers: Whether to check available containers

    Returns:
        Dict with planning results including stock status and requirements
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Build stock check requests from recipe
        requests = _build_recipe_requests(recipe, scale, check_containers=check_containers)
        
        # Use UniversalStockCheckService for individual item checks
        stock_service = UniversalStockCheckService()
        stock_results = stock_service.check_bulk_items(requests)

        # Process results into recipe-specific format
        processed_results = _process_stock_results(stock_results)
        
        # Only check ingredient availability for overall success
        ingredient_results = [r for r in processed_results if r.get('category') == 'ingredient']
        all_available = all(result['status'] in ['OK', 'AVAILABLE', 'LOW'] for result in ingredient_results)

        # Calculate requirements and costs
        requirements = calculate_recipe_requirements(recipe_id, scale)
        cost_info = calculate_production_cost(recipe_id, scale)

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale': scale,
            'stock_check': processed_results,
            'all_ok': all_available,
            'all_available': all_available,  # For backwards compatibility
            'requirements': requirements,
            'cost_info': cost_info,
            'stock_results': processed_results  # For backwards compatibility
        }

    except Exception as e:
        logger.error(f"Error in production planning: {e}")
        return {'success': False, 'error': str(e)}


def calculate_recipe_requirements(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate ingredient requirements for a recipe at given scale.

    Args:
        recipe_id: Recipe to calculate for
        scale: Scaling factor

    Returns:
        Dict with success status and ingredient requirements
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        ingredients = []
        for recipe_ingredient in recipe.recipe_ingredients:
            scaled_quantity = recipe_ingredient.quantity * scale

            ingredients.append({
                'ingredient_id': recipe_ingredient.inventory_item_id,
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'base_quantity': recipe_ingredient.quantity,
                'scaled_quantity': scaled_quantity,
                'unit': recipe_ingredient.unit,
                'cost_per_unit': getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0
            })

        return {
            'success': True,
            'ingredients': ingredients,
            'recipe_id': recipe_id,
            'scale': scale
        }

    except Exception as e:
        logger.error(f"Error calculating requirements for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def check_ingredient_availability(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check availability of all ingredients for a recipe.

    Args:
        recipe_id: Recipe to check
        scale: Scaling factor

    Returns:
        Dict with availability results
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Build requests for ingredients only
        requests = []
        for recipe_ingredient in recipe.recipe_ingredients:
            requests.append(StockCheckRequest(
                item_id=recipe_ingredient.inventory_item_id,
                quantity_needed=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                category=InventoryCategory.INGREDIENT,
                scale_factor=scale
            ))

        # Use stock service
        stock_service = UniversalStockCheckService()
        results = stock_service.check_bulk_items(requests)

        # Format results
        processed_results = _process_stock_results(results)
        all_available = all(result['status'] in ['OK', 'LOW'] for result in processed_results)

        return {
            'success': True,
            'all_available': all_available,
            'ingredients': processed_results,
            'recipe_id': recipe_id,
            'scale': scale
        }

    except Exception as e:
        logger.error(f"Error checking ingredient availability for recipe {recipe_id}: {e}")
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

        yield_amount = recipe.predicted_yield * scale if recipe.predicted_yield else 1.0

        for container in containers:
            # Only include containers that have stock
            if hasattr(container, 'quantity') and container.quantity > 0:
                requests.append(StockCheckRequest(
                    item_id=container.id,
                    quantity_needed=1,  # Check for at least 1 container
                    unit="count",
                    category=InventoryCategory.CONTAINER,
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
