"""
Core Universal Stock Check Service

Orchestrates stock checking across different inventory categories.
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

    Provides unified interface for checking stock availability across
    different inventory categories with category-specific handlers.
    """

    def __init__(self):
        self.handlers = {
            InventoryCategory.INGREDIENT: IngredientHandler(),
            InventoryCategory.CONTAINER: ContainerHandler(),
            InventoryCategory.PRODUCT: ProductHandler(),
            # Future: InventoryCategory.CONSUMABLE: ConsumableHandler()
        }

    def check_recipe_stock(self, recipe, scale: float = 1.0) -> Dict[str, Any]:
        """
        Check stock availability for all items in a recipe.

        Args:
            recipe: Recipe model instance
            scale: Scaling factor for quantities

        Returns:
            Dict with results and overall status
        """
        logger.info(f"Starting recipe stock check: {recipe.name}, scale: {scale}")

        requests = self._build_recipe_requests(recipe, scale)
        results = []
        overall_status = True

        for request in requests:
            try:
                result = self.check_single_item(request)
                results.append(result)

                if result.status.value in ['NEEDED', 'ERROR', 'DENSITY_MISSING']:
                    overall_status = False

            except Exception as e:
                logger.error(f"Error checking {request.category.value} {request.item_id}: {e}")
                # Add error result
                error_result = StockCheckResult(
                    item_id=request.item_id,
                    item_name=f"Unknown {request.category.value}",
                    category=request.category,
                    needed_quantity=request.quantity_needed,
                    needed_unit=request.unit,
                    available_quantity=0,
                    available_unit=request.unit,
                    status=StockStatus.ERROR,
                    error_message=str(e)
                )
                results.append(error_result)
                overall_status = False

        return {
            'stock_check': [r.to_dict() for r in results],
            'all_ok': overall_status,
            'recipe_id': recipe.id,
            'scale': scale
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

    def _build_recipe_requests(self, recipe, scale: float) -> List[StockCheckRequest]:
        """Build stock check requests from recipe"""
        requests = []

        # Add ingredient requests
        for recipe_ingredient in recipe.ingredients:
            requests.append(StockCheckRequest(
                item_id=recipe_ingredient.inventory_item_id,
                quantity_needed=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                category=InventoryCategory.INGREDIENT,
                scale_factor=scale
            ))

        # Add container requests if recipe has allowed containers
        if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
            # Calculate how many containers needed based on yield
            yield_amount = recipe.predicted_yield * scale if recipe.predicted_yield else 1.0

            for container_id in recipe.allowed_containers:
                requests.append(StockCheckRequest(
                    item_id=container_id,
                    quantity_needed=yield_amount,  # Will be converted by handler
                    unit=recipe.predicted_yield_unit or "count",
                    category=InventoryCategory.CONTAINER,
                    scale_factor=scale
                ))

        return requests


# Compatibility functions for existing code
def universal_stock_check(recipe, scale=1.0, flex_mode=False):
    """Legacy compatibility function"""
    service = UniversalStockCheckService()
    return service.check_recipe_stock(recipe, scale)


def check_stock_availability(inventory_requirements):
    """Legacy compatibility function for basic stock checking"""
    from ..universal_stock_check_service import check_stock_availability as legacy_check
    return legacy_check(inventory_requirements)