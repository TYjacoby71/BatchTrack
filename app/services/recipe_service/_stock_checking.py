
"""
Recipe Stock Checking Operations

Handles stock checking for recipes using the Universal Stock Check Service.
"""

import logging
from typing import Dict, Any, List
from flask_login import current_user

from ...models import Recipe, RecipeIngredient
from ..stock_check.core import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory, StockStatus

logger = logging.getLogger(__name__)


def check_recipe_stock(recipe: Recipe, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check stock for all ingredients in a recipe using USCS.
    
    Args:
        recipe: Recipe object
        scale: Scale factor for the recipe
        
    Returns:
        Dictionary with stock check results
    """
    try:
        if not hasattr(recipe, 'recipe_ingredients') or not recipe.recipe_ingredients:
            return {
                'success': True,
                'status': 'no_ingredients',
                'stock_check': [],
                'message': 'Recipe has no ingredients to check'
            }

        # Build USCS requests for all recipe ingredients
        requests = []
        organization_id = current_user.organization_id if current_user.is_authenticated else None
        
        for recipe_ingredient in recipe.recipe_ingredients:
            requests.append(StockCheckRequest(
                item_id=recipe_ingredient.inventory_item_id,
                quantity_needed=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                category=InventoryCategory.INGREDIENT,
                organization_id=organization_id
            ))

        # Use USCS for bulk checking
        uscs = UniversalStockCheckService()
        results = uscs.check_bulk_items(requests)
        
        # Convert results to dictionaries
        stock_check_data = []
        has_insufficient = False
        
        for result in results:
            result_dict = {
                'item_id': result.item_id,
                'item_name': result.item_name,
                'needed_quantity': result.needed_quantity,
                'needed_unit': result.needed_unit,
                'available_quantity': result.available_quantity,
                'available_unit': result.available_unit,
                'status': result.status.value,
                'formatted_needed': result.formatted_needed,
                'formatted_available': result.formatted_available
            }
            
            if hasattr(result, 'error_message') and result.error_message:
                result_dict['error_message'] = result.error_message
                
            if hasattr(result, 'conversion_details') and result.conversion_details:
                result_dict['conversion_details'] = result.conversion_details
                
            stock_check_data.append(result_dict)
            
            if result.status in [StockStatus.NEEDED, StockStatus.OUT_OF_STOCK]:
                has_insufficient = True

        return {
            'success': True,
            'status': 'insufficient_ingredients' if has_insufficient else 'ok',
            'stock_check': stock_check_data
        }

    except Exception as e:
        logger.error(f"Error in check_recipe_stock: {e}")
        return {
            'success': False,
            'status': 'error',
            'stock_check': [],
            'error': str(e)
        }


def get_recipe_ingredients_for_stock_check(recipe_id: int, scale: float = 1.0) -> List[StockCheckRequest]:
    """
    Get recipe ingredients formatted as stock check requests.
    This is used by bulk stock checking systems.
    
    Args:
        recipe_id: Recipe ID
        scale: Scale factor
        
    Returns:
        List of StockCheckRequest objects
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe or not recipe.recipe_ingredients:
            return []

        requests = []
        organization_id = current_user.organization_id if current_user.is_authenticated else None
        
        for recipe_ingredient in recipe.recipe_ingredients:
            requests.append(StockCheckRequest(
                item_id=recipe_ingredient.inventory_item_id,
                quantity_needed=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                category=InventoryCategory.INGREDIENT,
                organization_id=organization_id
            ))

        return requests

    except Exception as e:
        logger.error(f"Error getting recipe ingredients for stock check: {e}")
        return []
