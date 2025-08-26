"""
Container-specific stock checking handler
"""

import logging
from typing import Optional

from app.models import InventoryItem
from app.services.unit_conversion import ConversionEngine
from ..types import StockCheckRequest, StockCheckResult, StockStatus, InventoryCategory
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class ContainerHandler(BaseInventoryHandler):
    """Handler for container stock checking with storage capacity logic"""

    def check_availability(self, request: StockCheckRequest, organization_id: int = None) -> StockCheckResult:
        """Check container availability"""
        # Query-level organization filtering - never load unauthorized data
        container = InventoryItem.query.filter_by(
            id=request.item_id,
            type='container',
            organization_id=request.organization_id
        ).first()

        if not container:
            return self._create_not_found_result(request)

        # Containers have storage_amount and storage_unit fields
        storage_capacity = getattr(container, 'storage_amount', 0)
        storage_unit = getattr(container, 'storage_unit', 'ml')
        available_containers = container.quantity

        logger.debug(f"Container {container.name}: {available_containers} units, capacity {storage_capacity} {storage_unit}")

        try:
            # Calculate how many containers are needed
            # Convert product yield to container storage unit first
            if request.unit != storage_unit:
                conversion_result = ConversionEngine.convert_units(
                    request.quantity_needed,
                    request.unit,
                    storage_unit,
                    ingredient_id=request.item_id
                )

                if isinstance(conversion_result, dict):
                    yield_in_container_units = conversion_result['converted_value']
                    conversion_details = conversion_result
                else:
                    yield_in_container_units = float(conversion_result)
                    conversion_details = None
            else:
                yield_in_container_units = request.quantity_needed
                conversion_details = None

            # Calculate containers needed
            containers_needed = yield_in_container_units / storage_capacity if storage_capacity > 0 else 1
            containers_needed = max(1, int(containers_needed))  # At least 1 container

            # Check availability
            status = self._determine_status(available_containers, containers_needed)

            return StockCheckResult(
                item_id=container.id,
                item_name=container.name,
                category=InventoryCategory.CONTAINER,
                needed_quantity=containers_needed,
                needed_unit="count",
                available_quantity=available_containers,
                available_unit="count",
                raw_stock=available_containers,
                stock_unit="count",
                status=status,
                formatted_needed=self._format_quantity_display(containers_needed, "count"),
                formatted_available=self._format_quantity_display(available_containers, "count"),
                conversion_details={
                    **(conversion_details or {}),
                    'storage_capacity': storage_capacity,
                    'storage_unit': storage_unit,
                    'yield_in_storage_units': yield_in_container_units
                }
            )

        except (ValueError, ZeroDivisionError) as e:
            return StockCheckResult(
                item_id=container.id,
                item_name=container.name,
                category=InventoryCategory.CONTAINER,
                needed_quantity=1,
                needed_unit="count",
                available_quantity=available_containers,
                available_unit="count",
                status=StockStatus.ERROR,
                error_message=f"Container calculation error: {str(e)}",
                formatted_needed="1 count",
                formatted_available=self._format_quantity_display(available_containers, "count")
            )

    def get_item_details(self, item_id: int, organization_id: int) -> Optional[dict]:
        """Get container details"""
        container = InventoryItem.query.filter_by(
            id=item_id,
            organization_id=organization_id
        ).first()
        if not container:
            return None

        return {
            'id': container.id,
            'name': container.name,
            'unit': container.unit,
            'quantity': container.quantity,
            'storage_amount': getattr(container, 'storage_amount', 0),
            'storage_unit': getattr(container, 'storage_unit', 'ml'),
            'cost_per_unit': container.cost_per_unit,
            'type': container.type
        }

    def _create_not_found_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for container not found"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Unknown Container',
            category=InventoryCategory.CONTAINER,
            needed_quantity=1,
            needed_unit="count",
            available_quantity=0,
            available_unit="count",
            status=StockStatus.ERROR,
            error_message='Container not found',
            formatted_needed="1 count",
            formatted_available="0 count"
        )

    def _create_access_denied_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for access denied"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Access Denied',
            category=InventoryCategory.CONTAINER,
            needed_quantity=1,
            needed_unit="count",
            available_quantity=0,
            available_unit="count",
            status=StockStatus.ERROR,
            error_message='Access denied',
            formatted_needed="1 count",
            formatted_available="0 count"
        )

    def check_stock(self, request: StockCheckRequest) -> StockCheckResult:
        """Check container stock availability"""
        try:
            # Get the container item
            container = InventoryItem.query.get(request.item_id)
            if not container or container.type != 'container':
                return self._create_not_found_result(request)

            # Get current stock quantity
            available_quantity = container.quantity or 0

            # For containers, we typically check if we have enough units available
            needed_quantity = request.quantity_needed or 1

            # Determine status
            if available_quantity >= needed_quantity:
                status = StockStatus.AVAILABLE
            elif available_quantity > 0:
                status = StockStatus.LOW
            else:
                status = StockStatus.OUT_OF_STOCK

            return StockCheckResult(
                item_id=container.id,
                item_name=container.name,
                needed_quantity=needed_quantity,
                needed_unit=request.unit or 'count',
                available_quantity=available_quantity,
                available_unit=container.unit or 'count',
                status=status,
                category=InventoryCategory.CONTAINER,
                conversion_details={
                    'storage_capacity': getattr(container, 'storage_amount', 0),
                    'storage_unit': getattr(container, 'storage_unit', 'ml'),
                    'item_id': container.id,
                    'item_name': container.name,
                    'stock_qty': available_quantity
                }
            )
        except Exception as e:
            logger.error(f"Error checking container stock for item {request.item_id}: {e}")
            return self._create_error_result(request, str(e))