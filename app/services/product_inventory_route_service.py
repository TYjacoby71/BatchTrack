"""Product inventory route service boundary.

Synopsis:
Encapsulates SKU and lot data/session access used by
`products/product_inventory_routes.py` so routes stay transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_

from app.extensions import db
from app.models import ProductSKU
from app.models.inventory_lot import InventoryLot


class ProductInventoryRouteService:
    """Data/session helpers for product inventory routes."""

    @staticmethod
    def get_sku_for_inventory_item_org(
        *, inventory_item_id: int, organization_id: int | None
    ) -> ProductSKU | None:
        if not organization_id:
            return None
        return (
            ProductSKU.scoped()
            .filter_by(
                inventory_item_id=inventory_item_id,
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def find_sku_for_inventory_item(
        *, inventory_item_id: int, organization_id: int | None
    ) -> ProductSKU | None:
        return ProductInventoryRouteService.get_sku_for_inventory_item_org(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
        )

    @staticmethod
    def get_active_sku_by_code_for_org(
        *, sku_code: str, organization_id: int | None
    ) -> ProductSKU | None:
        if not organization_id:
            return None
        return (
            ProductSKU.scoped()
            .filter_by(
                sku_code=sku_code,
                organization_id=organization_id,
                is_active=True,
            )
            .first()
        )

    @staticmethod
    def find_active_sku_by_code(
        *, sku_code: str, organization_id: int | None
    ) -> ProductSKU | None:
        return ProductInventoryRouteService.get_active_sku_by_code_for_org(
            sku_code=sku_code,
            organization_id=organization_id,
        )

    @staticmethod
    def get_sku_by_id_for_org(
        *, sku_id: int, organization_id: int | None
    ) -> ProductSKU | None:
        if not organization_id:
            return None
        return (
            ProductSKU.scoped()
            .filter_by(id=sku_id, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def find_sku_by_id_for_org(
        *, sku_id: int, organization_id: int | None
    ) -> ProductSKU | None:
        return ProductInventoryRouteService.get_sku_by_id_for_org(
            sku_id=sku_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_fresh_lots_for_item_org(
        *,
        inventory_item_id: int,
        organization_id: int | None,
        today: date,
    ) -> list[InventoryLot]:
        if not organization_id:
            return []
        return (
            InventoryLot.scoped()
            .filter(
                InventoryLot.inventory_item_id == inventory_item_id,
                InventoryLot.organization_id == organization_id,
                InventoryLot.remaining_quantity_base > 0,
                or_(
                    InventoryLot.expiration_date.is_(None),
                    InventoryLot.expiration_date >= today,
                ),
            )
            .order_by(InventoryLot.received_date.asc())
            .all()
        )

    @staticmethod
    def list_fresh_inventory_lots(
        *,
        inventory_item_id: int,
        organization_id: int | None,
        today: date,
    ) -> list[InventoryLot]:
        return ProductInventoryRouteService.list_fresh_lots_for_item_org(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
            today=today,
        )

    @staticmethod
    def list_expired_lots_for_item_org(
        *,
        inventory_item_id: int,
        organization_id: int | None,
        today: date,
    ) -> list[InventoryLot]:
        if not organization_id:
            return []
        return (
            InventoryLot.scoped()
            .filter(
                InventoryLot.inventory_item_id == inventory_item_id,
                InventoryLot.organization_id == organization_id,
                InventoryLot.remaining_quantity_base > 0,
                InventoryLot.expiration_date.isnot(None),
                InventoryLot.expiration_date < today,
            )
            .order_by(InventoryLot.received_date.asc())
            .all()
        )

    @staticmethod
    def list_expired_inventory_lots(
        *,
        inventory_item_id: int,
        organization_id: int | None,
        today: date,
    ) -> list[InventoryLot]:
        return ProductInventoryRouteService.list_expired_lots_for_item_org(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
            today=today,
        )

    @staticmethod
    def sum_remaining_quantity(lots: list[InventoryLot]) -> float:
        return sum(float(lot.remaining_quantity or 0.0) for lot in lots)

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
