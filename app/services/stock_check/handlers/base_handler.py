"""
Base handler class for inventory category handlers
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..types import StockCheckRequest, StockCheckResult, StockStatus

logger = logging.getLogger(__name__)


class BaseInventoryHandler(ABC):
    """
    Base class for inventory category handlers.

    Each category handler is a simple helper that finds inventory items
    in that category and performs category-specific calculations.
    Organization scoping is handled by the core service.
    """

    @abstractmethod
    def check_availability(
        self, request: StockCheckRequest, organization_id: int
    ) -> StockCheckResult:
        """
        Check availability for a specific inventory item.

        Args:
            request: Stock check request
            organization_id: Organization ID for scoping

        Returns:
            Stock check result
        """
        pass

    @abstractmethod
    def get_item_details(self, item_id: int, organization_id: int) -> Optional[dict]:
        """
        Get details for an inventory item.

        Args:
            item_id: Item ID
            organization_id: Organization ID for scoping

        Returns:
            Item details dict or None if not found
        """
        pass

    def _format_quantity_display(self, quantity: float, unit: str) -> str:
        """Format quantity for display"""
        if quantity == int(quantity):
            return f"{int(quantity)} {unit}"
        return f"{quantity:.2f} {unit}"

    def _determine_status(self, available: float, needed: float) -> StockStatus:
        """Determine stock status based on available vs needed"""
        if available >= needed:
            return StockStatus.OK
        elif available >= needed * 0.5:
            return StockStatus.LOW
        else:
            return StockStatus.NEEDED
