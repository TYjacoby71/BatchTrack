"""
Core Universal Stock Check Service

Orchestrates stock checking for individual inventory items only.
Recipe logic should be handled by calling services.
"""

import logging
from typing import List, Dict, Any
from flask_login import current_user

from .types import StockCheckRequest, StockCheckResult, InventoryCategory, StockStatus
from .handlers import IngredientHandler, ContainerHandler, ProductHandler

logger = logging.getLogger(__name__)


class UniversalStockCheckService:
    """
    Universal Stock Check Service (USCS)

    Provides unified interface for checking stock availability of individual
    inventory items. Recipe logic is handled by calling services.
    Handles organization scoping and standardizes all results.
    """

    def __init__(self):
        self.handlers = {
            InventoryCategory.INGREDIENT: IngredientHandler(),
            InventoryCategory.CONTAINER: ContainerHandler(),
            InventoryCategory.PRODUCT: ProductHandler(),
        }

    def _get_organization_id(self, request: StockCheckRequest) -> int:
        """Get organization ID from request or current user"""
        if hasattr(request, 'organization_id') and request.organization_id:
            return request.organization_id
        elif current_user and current_user.is_authenticated and current_user.organization_id:
            return current_user.organization_id
        else:
            raise ValueError("No organization context available for stock check")

    def check_single_item(self, request: StockCheckRequest) -> StockCheckResult:
        """
        Check stock for a single inventory item with organization scoping.

        Args:
            request: Stock check request

        Returns:
            Standardized stock check result
        """
        try:
            # Ensure organization context
            org_id = self._get_organization_id(request)
            
            # Get appropriate handler
            handler = self.handlers.get(request.category)
            if not handler:
                return self._create_error_result(request, f"No handler for category: {request.category}")

            # Handler does the category-specific work
            result = handler.check_availability(request, org_id)
            
            # Standardize the result format
            return self._standardize_result(result)
            
        except Exception as e:
            logger.error(f"Error in check_single_item: {e}")
            return self._create_error_result(request, str(e))

    def check_bulk_items(self, requests: List[StockCheckRequest]) -> List[StockCheckResult]:
        """
        Check stock for multiple items efficiently with organization scoping.

        Args:
            requests: List of stock check requests

        Returns:
            List of stock check results
        """
        results = []

        # Process each request individually to ensure proper scoping
        for request in requests:
            try:
                # Ensure organization context for each request
                org_id = self._get_organization_id(request)
                
                # Get appropriate handler
                handler = self.handlers.get(request.category)
                if not handler:
                    error_result = self._create_error_result(request, f"No handler for category: {request.category}")
                    results.append(error_result)
                    continue

                # Handler does the category-specific work with organization scoping
                result = handler.check_availability(request, org_id)
                
                # Standardize the result format
                standardized_result = self._standardize_result(result)
                results.append(standardized_result)
                
            except Exception as e:
                logger.error(f"Error in bulk check for {request.category}: {e}")
                error_result = self._create_error_result(request, str(e))
                results.append(error_result)

        return results

    def _standardize_result(self, result: StockCheckResult) -> StockCheckResult:
        """Ensure all results have consistent format and required fields"""
        # All results should have these standard fields
        standardized = StockCheckResult(
            item_id=result.item_id,
            item_name=result.item_name,
            category=result.category,
            needed_quantity=result.needed_quantity,
            needed_unit=result.needed_unit,
            available_quantity=result.available_quantity,
            available_unit=result.available_unit,
            status=self._determine_final_status(result),
            raw_stock=getattr(result, 'raw_stock', result.available_quantity),
            stock_unit=getattr(result, 'stock_unit', result.available_unit),
            formatted_needed=getattr(result, 'formatted_needed', f"{result.needed_quantity} {result.needed_unit}"),
            formatted_available=getattr(result, 'formatted_available', f"{result.available_quantity} {result.available_unit}"),
            error_message=getattr(result, 'error_message', None),
            conversion_details=getattr(result, 'conversion_details', None)
        )
        
        return standardized

    def _determine_final_status(self, result: StockCheckResult) -> StockStatus:
        """Determine final status with low stock alert integration"""
        if result.status == StockStatus.ERROR:
            return StockStatus.ERROR
            
        # Check if we have enough
        if result.available_quantity >= result.needed_quantity:
            # Check if this item has low stock alerts set
            from ...models import InventoryItem
            item = InventoryItem.query.get(result.item_id)
            if item and item.low_stock_threshold and result.available_quantity <= item.low_stock_threshold:
                return StockStatus.LOW
            return StockStatus.OK
        
        # Not enough available
        if result.available_quantity > 0:
            return StockStatus.LOW
        else:
            return StockStatus.NEEDED

    def _create_error_result(self, request: StockCheckRequest, error_message: str) -> StockCheckResult:
        """Create standardized error result"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Unknown Item',
            category=request.category,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message=error_message,
            formatted_needed=f"{request.quantity_needed} {request.unit}",
            formatted_available="0"
        )

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
                requests = get_recipe_ingredients_for_stock_check(recipe_id, scale, organization_id)
                
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

    