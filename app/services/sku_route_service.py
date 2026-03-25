"""SKU route service boundary.

Synopsis:
Encapsulates SKU route data/session access so `products/sku.py` stays
transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import ProductSKU, Reservation, UnifiedInventoryHistory
from app.models.inventory_lot import InventoryLot


class SkuRouteService:
    """Data/session helpers for SKU route workflows."""

    @staticmethod
    def get_sku_or_404(*, inventory_item_id: int) -> ProductSKU:
        return (
            ProductSKU.scoped().filter_by(inventory_item_id=inventory_item_id).first_or_404()
        )

    @staticmethod
    def get_sku_for_org_or_404(
        *, inventory_item_id: int, organization_id: int | None
    ) -> ProductSKU:
        return (
            ProductSKU.scoped()
            .filter_by(
                inventory_item_id=inventory_item_id,
                organization_id=organization_id,
            )
            .first_or_404()
        )

    @staticmethod
    def get_org_sku_or_404(
        *, inventory_item_id: int, organization_id: int | None
    ) -> ProductSKU:
        return SkuRouteService.get_sku_for_org_or_404(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_sku_history_for_org(
        *, inventory_item_id: int, organization_id: int | None
    ) -> list[UnifiedInventoryHistory]:
        if not organization_id:
            return []
        return (
            UnifiedInventoryHistory.scoped()
            .filter_by(
                inventory_item_id=inventory_item_id,
                organization_id=organization_id,
            )
            .order_by(UnifiedInventoryHistory.timestamp.desc())
            .all()
        )

    @staticmethod
    def list_inventory_lots_for_item(*, inventory_item_id: int) -> list[InventoryLot]:
        return (
            InventoryLot.scoped()
            .filter(InventoryLot.inventory_item_id == inventory_item_id)
            .all()
        )

    @staticmethod
    def list_history_entries_for_lot(*, lot_id: int) -> list[UnifiedInventoryHistory]:
        return (
            UnifiedInventoryHistory.scoped()
            .filter(UnifiedInventoryHistory.affected_lot_id == lot_id)
            .all()
        )

    @staticmethod
    def list_history_entries_for_item(
        *, inventory_item_id: int
    ) -> list[UnifiedInventoryHistory]:
        return (
            UnifiedInventoryHistory.scoped()
            .filter(UnifiedInventoryHistory.inventory_item_id == inventory_item_id)
            .all()
        )

    @staticmethod
    def list_active_skus_for_org(*, organization_id: int | None) -> list[ProductSKU]:
        if not organization_id:
            return []
        return (
            ProductSKU.scoped()
            .filter(
                ProductSKU.organization_id == organization_id,
                ProductSKU.is_active,
            )
            .order_by(ProductSKU.product_id, ProductSKU.variant_id, ProductSKU.size_label)
            .all()
        )

    @staticmethod
    def list_active_org_skus_for_merge(
        *, organization_id: int | None
    ) -> list[ProductSKU]:
        return SkuRouteService.list_active_skus_for_org(organization_id=organization_id)

    @staticmethod
    def list_skus_for_merge_ids_for_org(
        *, sku_inventory_item_ids: list[str], organization_id: int | None
    ) -> list[ProductSKU]:
        if not organization_id or not sku_inventory_item_ids:
            return []
        return (
            ProductSKU.scoped()
            .filter(
                ProductSKU.inventory_item_id.in_(sku_inventory_item_ids),
                ProductSKU.organization_id == organization_id,
            )
            .all()
        )

    @staticmethod
    def list_org_skus_by_inventory_ids(
        *, inventory_item_ids: list[str], organization_id: int | None
    ) -> list[ProductSKU]:
        return SkuRouteService.list_skus_for_merge_ids_for_org(
            sku_inventory_item_ids=inventory_item_ids,
            organization_id=organization_id,
        )

    @staticmethod
    def reassign_history_inventory_item(
        *, from_inventory_item_id: int, to_inventory_item_id: int
    ) -> None:
        UnifiedInventoryHistory.scoped().filter_by(
            inventory_item_id=from_inventory_item_id
        ).update({"inventory_item_id": to_inventory_item_id})

    @staticmethod
    def repoint_history_inventory_item(
        *, from_inventory_item_id: int, to_inventory_item_id: int
    ) -> None:
        SkuRouteService.reassign_history_inventory_item(
            from_inventory_item_id=from_inventory_item_id,
            to_inventory_item_id=to_inventory_item_id,
        )

    @staticmethod
    def reassign_reservations_product_item(
        *, from_inventory_item_id: int, to_inventory_item_id: int
    ) -> None:
        Reservation.scoped().filter_by(product_item_id=from_inventory_item_id).update(
            {"product_item_id": to_inventory_item_id}
        )

    @staticmethod
    def repoint_reservations_product_item(
        *, from_inventory_item_id: int, to_inventory_item_id: int
    ) -> None:
        SkuRouteService.reassign_reservations_product_item(
            from_inventory_item_id=from_inventory_item_id,
            to_inventory_item_id=to_inventory_item_id,
        )

    @staticmethod
    def delete_sku_and_inventory_item(*, sku: ProductSKU) -> None:
        if sku.inventory_item is not None:
            db.session.delete(sku.inventory_item)
        db.session.delete(sku)

    @staticmethod
    def delete_inventory_item_and_sku(*, source_sku: ProductSKU) -> None:
        SkuRouteService.delete_sku_and_inventory_item(sku=source_sku)

    @staticmethod
    def count_history_entries_for_item(*, inventory_item_id: int) -> int:
        return UnifiedInventoryHistory.scoped().filter_by(
            inventory_item_id=inventory_item_id
        ).count()

    @staticmethod
    def count_active_reservations_for_item(
        *, inventory_item_id: int | None = None, product_item_id: int | None = None
    ) -> int:
        resolved_product_item_id = (
            product_item_id if product_item_id is not None else inventory_item_id
        )
        if resolved_product_item_id is None:
            return 0
        return Reservation.scoped().filter_by(
            product_item_id=resolved_product_item_id, status="active"
        ).count()

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
