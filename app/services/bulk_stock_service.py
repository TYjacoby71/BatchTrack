
"""
Bulk Stock Check Service

Handles checking stock for multiple recipes efficiently.
"""

import logging
from typing import Dict, Any, List
from flask_login import current_user

from ..models import Recipe
from .stock_check import UniversalStockCheckService
from .recipe_service._stock_checking import get_recipe_ingredients_for_stock_check

logger = logging.getLogger(__name__)


class BulkStockCheckService:
    """Service for checking stock across multiple recipes efficiently."""
    
    def __init__(self):
        self.uscs = UniversalStockCheckService()
    
    def check_multiple_recipes(self, recipe_ids: List[int], scale: float = 1.0) -> Dict[str, Any]:
        """
        Check stock for multiple recipes at once.
        
        Args:
            recipe_ids: List of recipe IDs to check
            scale: Scale factor to apply to all recipes
            
        Returns:
            Dictionary with results for each recipe
        """
        try:
            results = {}
            
            for recipe_id in recipe_ids:
                recipe = Recipe.query.get(recipe_id)
                if not recipe:
                    results[str(recipe_id)] = {
                        'success': False,
                        'error': 'Recipe not found'
                    }
                    continue
                
                # Get stock check requests for this recipe
                requests = get_recipe_ingredients_for_stock_check(recipe_id, scale)
                
                if not requests:
                    results[str(recipe_id)] = {
                        'success': True,
                        'status': 'no_ingredients',
                        'stock_check': [],
                        'recipe_name': recipe.name
                    }
                    continue
                
                # Check stock using USCS
                stock_results = self.uscs.check_bulk_items(requests)
                
                # Format results
                stock_check_data = []
                has_insufficient = False
                
                for result in stock_results:
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
                    
                    stock_check_data.append(result_dict)
                    
                    if result.status.value in ['NEEDED', 'OUT_OF_STOCK']:
                        has_insufficient = True
                
                results[str(recipe_id)] = {
                    'success': True,
                    'status': 'insufficient_ingredients' if has_insufficient else 'ok',
                    'stock_check': stock_check_data,
                    'recipe_name': recipe.name
                }
            
            return {
                'success': True,
                'results': results,
                'scale': scale
            }
            
        except Exception as e:
            logger.error(f"Error in bulk stock check: {e}")
            return {
                'success': False,
                'error': str(e)
            }
