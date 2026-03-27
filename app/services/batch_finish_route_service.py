"""Batch finish route data-access boundary.

Synopsis:
Owns batch-finish route query/session operations so
`app/blueprints/batches/finish_batch.py` can stay orchestration-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Batch, InventoryItem, Product, ProductVariant
from app.models.inventory_lot import InventoryLot
from app.models.product import ProductSKU
from app.models.product_category import ProductCategory


class BatchFinishRouteService:
    """Query/session helpers for batch finish flows."""

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def add_and_flush(instance) -> None:
        db.session.add(instance)
        db.session.flush()

    @staticmethod
    def get_in_progress_batch(*, batch_id: int, organization_id: int | None):
        query = Batch.scoped().filter_by(id=batch_id, status="in_progress")
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query.first()

    @staticmethod
    def list_existing_skus_for_product_variant(
        *, product_id: int, variant_id: int, organization_id: int | None
    ):
        query = (
            ProductSKU.scoped()
            .join(ProductSKU.inventory_item)
            .filter(
                ProductSKU.product_id == product_id,
                ProductSKU.variant_id == variant_id,
            )
        )
        if organization_id:
            query = query.filter(InventoryItem.organization_id == organization_id)
        return query.all()

    @staticmethod
    def get_batch_stats(*, batch_id: int):
        from app.models.statistics import BatchStats

        return BatchStats.query.filter_by(batch_id=batch_id).first()

    @staticmethod
    def find_inventory_item_by_name_and_org(*, name: str, organization_id: int | None):
        return (
            InventoryItem.scoped()
            .filter_by(name=name, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_scoped_product(*, product_id: int, organization_id: int | None):
        return (
            Product.scoped()
            .filter_by(id=product_id, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_scoped_variant(
        *, variant_id: int, product_id: int, organization_id: int | None
    ):
        return (
            ProductVariant.scoped()
            .filter_by(
                id=variant_id,
                product_id=product_id,
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def get_product_any_scope(*, product_id: int):
        return Product.scoped().filter_by(id=product_id).first()

    @staticmethod
    def get_variant_any_scope(*, variant_id: int, product_id: int):
        return (
            ProductVariant.scoped()
            .filter_by(id=variant_id, product_id=product_id)
            .first()
        )

    @staticmethod
    def get_sku_for_variant_and_size(
        *, product_id: int, variant_id: int, size_label: str
    ):
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                variant_id=variant_id,
                size_label=size_label,
            )
            .first()
        )

    @staticmethod
    def get_product_category(*, category_id: int | None):
        if not category_id:
            return None
        return db.session.get(ProductCategory, category_id)

    @staticmethod
    def get_scoped_inventory_item(
        *, inventory_item_id: int, organization_id: int | None
    ):
        return (
            InventoryItem.scoped()
            .filter_by(id=inventory_item_id, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_latest_lot_for_batch(*, inventory_item_id: int, batch_id: int):
        return (
            InventoryLot.scoped()
            .filter_by(inventory_item_id=inventory_item_id, batch_id=batch_id)
            .order_by(InventoryLot.created_at.desc())
            .first()
        )
