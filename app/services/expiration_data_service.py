"""Expiration data access service.

Synopsis:
Owns expiration-related ORM/scoped queries and transaction helpers so
`app/blueprints/expiration/services.py` can focus on expiration rules.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Batch,
    InventoryHistory,
    InventoryItem,
    InventoryLot,
    Product,
    ProductSKU,
    ProductVariant,
    UnifiedInventoryHistory,
)


class ExpirationDataService:
    """Persistence/query helpers for expiration workflows."""

    @staticmethod
    def get_unified_history_entry_or_404(*, fifo_id: int):
        return UnifiedInventoryHistory.scoped().filter_by(id=fifo_id).first_or_404()

    @staticmethod
    def list_debug_product_lots(*, organization_id: int | None):
        query = (
            InventoryLot.scoped()
            .join(InventoryItem, InventoryLot.inventory_item_id == InventoryItem.id)
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.type == "product",
                    (
                        InventoryItem.organization_id == organization_id
                        if organization_id
                        else True
                    ),
                )
            )
        )
        return query.all()

    @staticmethod
    def get_inventory_item(*, inventory_item_id: int):
        return db.session.get(InventoryItem, inventory_item_id)

    @staticmethod
    def get_batch(*, batch_id: int):
        return db.session.get(Batch, batch_id)

    @staticmethod
    def list_fifo_lots(*, now_utc, expired: bool = False, days_ahead: int | None = None):
        query = (
            InventoryLot.scoped()
            .join(InventoryItem)
            .options(joinedload(InventoryLot.inventory_item))
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.is_perishable,
                )
            )
        )
        if expired:
            query = query.filter(
                and_(
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < now_utc,
                )
            )
        elif days_ahead:
            future_date_utc = now_utc + timedelta(days=days_ahead)
            query = query.filter(
                and_(
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date >= now_utc,
                    InventoryLot.expiration_date <= future_date_utc,
                )
            )
        return query.order_by(InventoryLot.expiration_date.asc()).all()

    @staticmethod
    def list_perishable_product_lots():
        query = (
            InventoryLot.scoped()
            .join(InventoryItem, InventoryLot.inventory_item_id == InventoryItem.id)
            .join(
                ProductSKU,
                ProductSKU.inventory_item_id == InventoryLot.inventory_item_id,
            )
            .options(joinedload(InventoryLot.inventory_item))
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.type == "product",
                    InventoryItem.is_perishable,
                )
            )
        )
        return query.all()

    @staticmethod
    def get_product_sku_by_inventory_item(*, inventory_item_id: int):
        return ProductSKU.scoped().filter_by(inventory_item_id=inventory_item_id).first()

    @staticmethod
    def get_product(*, product_id: int):
        return db.session.get(Product, product_id)

    @staticmethod
    def get_product_variant(*, variant_id: int):
        return db.session.get(ProductVariant, variant_id)

    @staticmethod
    def list_active_lots_for_item(*, inventory_item_id: int):
        return (
            InventoryLot.scoped()
            .filter(
                and_(
                    InventoryLot.inventory_item_id == inventory_item_id,
                    InventoryLot.remaining_quantity_base > 0,
                )
            )
            .all()
        )

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def list_lots_for_item_expiration_status(
        *, inventory_item_id: int, organization_id: int | None
    ):
        base_filter = [
            InventoryLot.inventory_item_id == inventory_item_id,
            InventoryLot.remaining_quantity_base > 0,
            InventoryLot.expiration_date.isnot(None),
        ]
        if organization_id:
            base_filter.append(InventoryLot.organization_id == organization_id)
        return InventoryLot.scoped().filter(and_(*base_filter)).all()

    @staticmethod
    def list_lots_for_weighted_freshness(*, inventory_item_id: int):
        return (
            InventoryLot.scoped()
            .filter(
                and_(
                    InventoryLot.inventory_item_id == inventory_item_id,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                )
            )
            .all()
        )

    @staticmethod
    def get_lot(*, lot_id: int):
        return db.session.get(InventoryLot, lot_id)

    @staticmethod
    def get_unified_history(*, entry_id: int):
        return db.session.get(UnifiedInventoryHistory, entry_id)

    @staticmethod
    def get_inventory_history(*, entry_id: int):
        return db.session.get(InventoryHistory, entry_id)

    @staticmethod
    def list_lots_expiring_within(*, now_utc, future_date):
        query = (
            InventoryLot.scoped()
            .join(InventoryItem)
            .filter(
                and_(
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date >= now_utc,
                    InventoryLot.expiration_date <= future_date,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.is_perishable,
                )
            )
        )
        return query.order_by(InventoryLot.expiration_date.asc()).all()

    @staticmethod
    def list_expired_lots(*, now_utc):
        return (
            InventoryLot.scoped()
            .join(InventoryItem)
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < now_utc,
                    InventoryItem.is_perishable,
                )
            )
            .all()
        )

    @staticmethod
    def list_expiring_soon_lots(*, now_utc, cutoff_date_utc):
        return (
            InventoryLot.scoped()
            .join(InventoryItem)
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date > now_utc,
                    InventoryLot.expiration_date <= cutoff_date_utc,
                    InventoryItem.is_perishable,
                )
            )
            .all()
        )
