"""
Product-specific stock checking handler
"""

import logging
from typing import Optional

from app.models import InventoryItem

from ..types import InventoryCategory, StockCheckRequest, StockCheckResult, StockStatus
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class ProductHandler(BaseInventoryHandler):
    """Handler for product stock checking"""

    def check_availability(
        self, request: StockCheckRequest, organization_id: int
    ) -> StockCheckResult:
        """
        Check product availability.

        Args:
            request: Stock check request
            organization_id: Organization ID for scoping

        Returns:
            Stock check result
        """
        product = InventoryItem.query.filter_by(
            id=request.item_id, type="product", organization_id=organization_id
        ).first()

        if not product:
            return self._create_not_found_result(request)

        available_quantity = product.quantity
        status = self._determine_status(available_quantity, request.quantity_needed)

        return StockCheckResult(
            item_id=product.id,
            item_name=product.name,
            category=InventoryCategory.PRODUCT,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=available_quantity,
            available_unit=product.unit,
            raw_stock=available_quantity,
            stock_unit=product.unit,
            status=status,
            formatted_needed=self._format_quantity_display(
                request.quantity_needed, request.unit
            ),
            formatted_available=self._format_quantity_display(
                available_quantity, product.unit
            ),
        )

    def get_item_details(self, item_id: int, organization_id: int) -> Optional[dict]:
        """Get product details"""
        product = InventoryItem.query.filter_by(
            id=item_id, organization_id=organization_id
        ).first()
        if not product:
            return None

        return {
            "id": product.id,
            "name": product.name,
            "unit": product.unit,
            "quantity": product.quantity,
            "cost_per_unit": product.cost_per_unit,
            "type": product.type,
        }

    def _create_not_found_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for product not found"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name="Unknown Product",
            category=InventoryCategory.PRODUCT,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message="Product not found",
            formatted_needed=self._format_quantity_display(
                request.quantity_needed, request.unit
            ),
            formatted_available="0",
        )

    def _create_access_denied_result(
        self, request: StockCheckRequest
    ) -> StockCheckResult:
        """Create result for access denied"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name="Access Denied",
            category=InventoryCategory.PRODUCT,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message="Access denied",
            formatted_needed=self._format_quantity_display(
                request.quantity_needed, request.unit
            ),
            formatted_available="0",
        )
