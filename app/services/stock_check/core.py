"""
Core Universal Stock Check Service

Orchestrates stock checking for individual inventory items only.
Recipe logic should be handled by calling services.
"""

import logging
from typing import List, Dict, Any

from .types import StockCheckRequest, StockCheckResult, InventoryCategory, StockStatus
from .handlers import IngredientHandler, ContainerHandler, ProductHandler

logger = logging.getLogger(__name__)


class UniversalStockCheckService:
    """
    Universal Stock Check Service (USCS)

    Provides unified interface for checking stock availability of individual
    inventory items. Recipe logic is handled by calling services.
    """

    def __init__(self):
        self.handlers = {
            InventoryCategory.INGREDIENT: IngredientHandler(),
            InventoryCategory.CONTAINER: ContainerHandler(),
            InventoryCategory.PRODUCT: ProductHandler(),
        }

    def check_single_item(self, request: StockCheckRequest) -> StockCheckResult:
        """
        Check stock for a single inventory item.

        Args:
            request: Stock check request

        Returns:
            Stock check result
        """
        handler = self.handlers.get(request.category)
        if not handler:
            raise ValueError(f"No handler for category: {request.category}")

        return handler.check_availability(request)

    def check_bulk_items(self, requests: List[StockCheckRequest]) -> List[StockCheckResult]:
        """
        Check stock for multiple items efficiently.

        Args:
            requests: List of stock check requests

        Returns:
            List of stock check results
        """
        results = []

        # Group requests by category for efficient batch processing
        by_category = {}
        for request in requests:
            if request.category not in by_category:
                by_category[request.category] = []
            by_category[request.category].append(request)

        # Process each category
        for category, category_requests in by_category.items():
            handler = self.handlers.get(category)
            if handler:
                for request in category_requests:
                    try:
                        result = handler.check_availability(request)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error in bulk check for {category}: {e}")
                        # Continue with other items

        return results

    def check_multiple_recipes(self, recipe_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check stock for multiple recipes at different scales.
        
        Args:
            recipe_configs: List of dicts with keys: recipe_id, scale, organization_id
            
        Returns:
            Dictionary with results for each recipe
        """
        try:
            from ...models import Recipe
            from ..recipe_service._stock_checking import get_recipe_ingredients_for_stock_check
            
            results = {}
            
            for config in recipe_configs:
                recipe_id = config.get('recipe_id')
                scale = config.get('scale', 1.0)
                organization_id = config.get('organization_id')
                
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
                stock_results = self.check_bulk_items(requests)
                
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
                    'recipe_name': recipe.name,
                    'scale': scale
                }
            
            return {
                'success': True,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in bulk recipe check: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    