"""
Base handler class for inventory category handlers
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional
from flask_login import current_user

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

    def _check_organization_access(self, item) -> bool:
        """Check if current user has access to this item"""
        if not current_user or not current_user.is_authenticated:
            return False

        if not current_user.organization_id:
            return current_user.user_type == 'developer'

        return hasattr(item, 'organization_id') and item.organization_id == current_user.organization_id

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