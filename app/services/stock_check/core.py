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