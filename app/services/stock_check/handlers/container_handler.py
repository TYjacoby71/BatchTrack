"""
Container-specific stock checking handler
"""

import logging
from typing import Optional

from app.models import InventoryItem, db
from app.services.unit_conversion.unit_conversion import ConversionEngine

from ..types import InventoryCategory, StockCheckRequest, StockCheckResult, StockStatus
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class ContainerHandler(BaseInventoryHandler):
    """Handler for container stock checking with storage capacity logic"""

    def check_availability(
        self, request: StockCheckRequest, organization_id: int = None
    ) -> StockCheckResult:
        """Check container availability for a recipe yield"""
        logger.info("CONTAINER_HANDLER: check_availability called")
        logger.info(f"CONTAINER_HANDLER: - request.item_id: {request.item_id}")
        logger.info(
            f"CONTAINER_HANDLER: - request.quantity_needed: {request.quantity_needed}"
        )
        logger.info(f"CONTAINER_HANDLER: - request.unit: {request.unit}")
        logger.info(
            f"CONTAINER_HANDLER: - request.organization_id: {request.organization_id}"
        )
        logger.info(f"CONTAINER_HANDLER: - organization_id param: {organization_id}")

        # For containers, we need to find containers that can hold the recipe yield
        # request.item_id is NOT a container ID - it's the recipe or ingredient context
        # We need to find available containers based on the yield requirements

        org_id_to_use = request.organization_id or organization_id
        logger.info(f"CONTAINER_HANDLER: Using organization_id: {org_id_to_use}")

        # Get all available containers for this organization
        available_containers_query = InventoryItem.query.filter_by(
            type="container", organization_id=org_id_to_use
        ).filter(InventoryItem.quantity > 0)

        logger.info(
            f"CONTAINER_HANDLER: Query SQL would be looking for type='container', organization_id={org_id_to_use}, quantity > 0"
        )

        available_containers = available_containers_query.all()
        logger.info(
            f"CONTAINER_HANDLER: Found {len(available_containers)} containers in database"
        )

        for cont in available_containers:
            logger.info(
                f"CONTAINER_HANDLER: - {cont.container_display_name} (ID: {cont.id}, qty: {cont.quantity})"
            )
            logger.info(
                f"CONTAINER_HANDLER: - Capacity: {getattr(cont, 'capacity', 'None')} {getattr(cont, 'capacity_unit', 'None')}"
            )

        if not available_containers:
            logger.warning(
                "CONTAINER_HANDLER: No containers found, returning not_found_result"
            )
            return self._create_not_found_result(request)

        # For now, return the first suitable container
        # TODO: This should be enhanced to return the best container option
        container = available_containers[0]
        logger.info(
            f"CONTAINER_HANDLER: Using container: {container.container_display_name}"
        )

        # Containers have capacity and capacity_unit fields
        storage_capacity = getattr(container, "capacity", 0)
        storage_unit = getattr(container, "capacity_unit", "ml")
        available_quantity = container.quantity

        logger.info(
            f"CONTAINER_HANDLER: Container {container.container_display_name}: {available_quantity} units, capacity {storage_capacity} {storage_unit}"
        )

        try:
            # Convert container capacity to recipe yield unit for proper comparison
            if request.unit != storage_unit:
                conversion_result = ConversionEngine.convert_units(
                    storage_capacity,
                    storage_unit,
                    request.unit,
                    ingredient_id=None,  # Containers don't need ingredient context for volume conversions
                )

                if isinstance(conversion_result, dict):
                    storage_capacity_in_recipe_units = conversion_result[
                        "converted_value"
                    ]
                    conversion_details = conversion_result
                else:
                    storage_capacity_in_recipe_units = float(conversion_result)
                    conversion_details = None
            else:
                storage_capacity_in_recipe_units = storage_capacity
                conversion_details = None

            # Calculate containers needed based on recipe yield unit
            containers_needed = (
                request.quantity_needed / storage_capacity_in_recipe_units
                if storage_capacity_in_recipe_units > 0
                else 1
            )
            containers_needed = max(1, int(containers_needed))  # At least 1 container

            # For container management, we always return OK if any containers exist
            # The container management system will handle its own logic about quantities needed
            if len(available_containers) > 0:
                status = StockStatus.OK
            else:
                status = StockStatus.OUT_OF_STOCK

            return StockCheckResult(
                item_id=container.id,
                item_name=container.container_display_name,
                category=InventoryCategory.CONTAINER,
                needed_quantity=containers_needed,
                needed_unit="count",
                available_quantity=len(available_containers),
                available_unit="count",
                raw_stock=len(available_containers),
                stock_unit="count",
                status=status,
                formatted_needed=self._format_quantity_display(
                    containers_needed, "count"
                ),
                formatted_available=self._format_quantity_display(
                    len(available_containers), "count"
                ),
                conversion_details={
                    **(conversion_details or {}),
                    "capacity": storage_capacity,
                    "capacity_unit": storage_unit,
                    "capacity_in_recipe_units": storage_capacity_in_recipe_units,
                    "recipe_yield_needed": request.quantity_needed,
                    "recipe_yield_unit": request.unit,
                },
            )

        except (ValueError, ZeroDivisionError) as e:
            # Build the result - ensure we handle quantity properly
            available_qty = container.quantity
            if isinstance(available_qty, (list, tuple)):
                available_qty = available_qty[0] if available_qty else 0
            elif available_qty is None:
                available_qty = 0

            # Get capacity
            storage_capacity = getattr(container, "capacity", None)

            return StockCheckResult(
                item_id=container.id,
                item_name=container.container_display_name,
                category=InventoryCategory.CONTAINER,
                needed_quantity=1,
                needed_unit="count",
                available_quantity=len(available_containers),
                available_unit="count",
                status=StockStatus.ERROR,
                error_message=f"Container calculation error: {str(e)}",
                formatted_needed="1 count",
                formatted_available=self._format_quantity_display(
                    len(available_containers), "count"
                ),
            )

    def get_item_details(self, item_id: int, organization_id: int) -> Optional[dict]:
        """Get container details"""
        container = InventoryItem.query.filter_by(
            id=item_id, organization_id=organization_id
        ).first()
        if not container:
            return None

        return {
            "id": container.id,
            "name": container.container_display_name,
            "unit": container.unit,
            "quantity": container.quantity,
            "capacity": getattr(container, "capacity", 0),
            "capacity_unit": getattr(container, "capacity_unit", "ml"),
            "cost_per_unit": container.cost_per_unit,
            "type": container.type,
        }

    def _create_not_found_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for container not found"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name="Unknown Container",
            category=InventoryCategory.CONTAINER,
            needed_quantity=1,
            needed_unit="count",
            available_quantity=0,
            available_unit="count",
            status=StockStatus.ERROR,
            error_message="Container not found",
            formatted_needed="1 count",
            formatted_available="0 count",
        )

    def _create_access_denied_result(
        self, request: StockCheckRequest
    ) -> StockCheckResult:
        """Create result for access denied"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name="Access Denied",
            category=InventoryCategory.CONTAINER,
            needed_quantity=1,
            needed_unit="count",
            available_quantity=0,
            available_unit="count",
            status=StockStatus.ERROR,
            error_message="Access denied",
            formatted_needed="1 count",
            formatted_available="0 count",
        )

    def check_stock(self, request: StockCheckRequest) -> StockCheckResult:
        """Check container stock availability"""
        try:
            # Get the container item
            container = db.session.get(InventoryItem, request.item_id)
            if not container or container.type != "container":
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
                item_name=container.container_display_name,
                needed_quantity=needed_quantity,
                needed_unit=request.unit or "count",
                available_quantity=available_quantity,
                available_unit=container.unit or "count",
                status=status,
                category=InventoryCategory.CONTAINER,
                conversion_details={
                    "capacity": getattr(container, "capacity", 0),
                    "capacity_unit": getattr(container, "capacity_unit", "ml"),
                    "item_id": container.id,
                    "item_name": container.container_display_name,
                    "stock_qty": available_quantity,
                },
            )
        except Exception as e:
            logger.error(
                f"Error checking container stock for item {request.item_id}: {e}"
            )
            return self._create_error_result(request, str(e))
