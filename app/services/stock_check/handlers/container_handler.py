"""
Container-specific stock checking handler
"""

import logging
from typing import Optional

from app.models import InventoryItem
from app.services.unit_conversion.unit_conversion import ConversionEngine
from ..types import StockCheckRequest, StockCheckResult, StockStatus, InventoryCategory
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class ContainerHandler(BaseInventoryHandler):
    """Handler for container stock checking with storage capacity logic"""

    def check_availability(self, request: StockCheckRequest, organization_id: int = None) -> StockCheckResult:
        """Check container availability for a recipe yield - delegates to production planning"""
        logger.info(f"CONTAINER_HANDLER: Delegating to production planning for container analysis")
        
        # Container stock checking is handled by production planning's container management
        # This handler just returns a basic availability check
        org_id_to_use = request.organization_id or organization_id
        
        # Get basic container count for this organization
        available_count = InventoryItem.query.filter_by(
            type='container',
            organization_id=org_id_to_use
        ).filter(InventoryItem.quantity > 0).count()
        
        logger.info(f"CONTAINER_HANDLER: Found {available_count} available containers")
        
        if available_count > 0:
            status = StockStatus.OK
        else:
            status = StockStatus.OUT_OF_STOCK
            
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Containers Available',
            category=InventoryCategory.CONTAINER,
            needed_quantity=1,
            needed_unit="count",
            available_quantity=available_count,
            available_unit="count",
            raw_stock=available_count,
            stock_unit="count",
            status=status,
            formatted_needed="1 count",
            formatted_available=f"{available_count} count",
            conversion_details={
                'total_containers_available': available_count,
                'organization_id': org_id_to_use,
                'delegated_to_production_planning': True
            }
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