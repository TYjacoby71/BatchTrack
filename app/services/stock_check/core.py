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

    def check_recipe_stock(self, recipe, scale: float = 1.0) -> dict:
        """
        Check stock for all ingredients in a recipe.

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

            requests = []
            for recipe_ingredient in recipe.recipe_ingredients:
                requests.append(StockCheckRequest(
                    item_id=recipe_ingredient.inventory_item_id,
                    quantity_needed=recipe_ingredient.quantity * scale,
                    unit=recipe_ingredient.unit,
                    category=InventoryCategory.INGREDIENT
                ))

            results = self.check_bulk_items(requests)
            
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