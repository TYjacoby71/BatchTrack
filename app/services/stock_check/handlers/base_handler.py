"""
Base handler class for inventory category handlers
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional
from flask_login import current_user

from app.models import InventoryItem
from ..types import StockCheckRequest, StockCheckResult, StockStatus

logger = logging.getLogger(__name__)


class BaseInventoryHandler(ABC):
    """
    Base class for inventory category handlers.

    Each category (ingredients, containers, products, etc.) should inherit
    from this class and implement the category-specific logic.
    """

    @abstractmethod
    def check_availability(self, request: StockCheckRequest) -> StockCheckResult:
        """
        Check availability for a specific inventory item.

        Args:
            request: Stock check request

        Returns:
            Stock check result
        """
        pass

    @abstractmethod
    def get_item_details(self, item_id: int) -> Optional[dict]:
        """
        Get details for an inventory item.

        Args:
            item_id: Item ID

        Returns:
            Item details dict or None if not found
        """
        pass

    # Removed _check_organization_access - using query-level filtering instead

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

    def _create_error_result(self, request: StockCheckRequest, error_message: str) -> StockCheckResult:
        """Create an error result for any handler"""
        from ..types import StockCheckResult, InventoryCategory
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Error',
            category=request.category,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message=error_message,
            formatted_needed=self._format_quantity_display(request.quantity_needed, request.unit),
            formatted_available="0"
        )