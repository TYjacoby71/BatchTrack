"""Inventory route data-access boundary.

Synopsis:
Owns inventory route query/session operations so
`app/blueprints/inventory/routes.py` can stay transport-focused.
"""

from __future__ import annotations

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    GlobalItem,
    IngredientCategory,
    InventoryItem,
    UnifiedInventoryHistory,
    Unit,
)
from app.models.inventory_lot import InventoryLot


class InventoryRouteService:
    """Data/session helpers for inventory routes."""

    @staticmethod
    def list_expired_quantity_rows(*, item_ids: list[int], today):
        return (
            db.session.query(
                InventoryLot.inventory_item_id,
                func.sum(InventoryLot.remaining_quantity_base),
            )
            .filter(
                InventoryLot.inventory_item_id.in_(item_ids),
                InventoryLot.remaining_quantity_base > 0,
                InventoryLot.expiration_date.is_not(None),
                InventoryLot.expiration_date < today,
            )
            .group_by(InventoryLot.inventory_item_id)
            .all()
        )

    @staticmethod
    def build_inventory_item_org_query(*, organization_id: int | None):
        query = InventoryItem.query
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query

    @staticmethod
    def get_inventory_item_by_id_for_org(*, item_id: int, organization_id: int | None):
        query = InventoryRouteService.build_inventory_item_org_query(
            organization_id=organization_id
        )
        return query.filter_by(id=item_id).first()

    @staticmethod
    def get_global_item(*, global_item_id: int):
        return db.session.get(GlobalItem, global_item_id)

    @staticmethod
    def add_unified_inventory_history(**kwargs):
        db.session.add(UnifiedInventoryHistory(**kwargs))

    @staticmethod
    def get_inventory_item(*, item_id: int):
        return db.session.get(InventoryItem, item_id)

    @staticmethod
    def list_active_units():
        return Unit.scoped().filter(Unit.is_active).all()

    @staticmethod
    def list_scoped_ingredient_categories():
        return IngredientCategory.scoped().order_by(IngredientCategory.name.asc()).all()

    @staticmethod
    def build_inventory_list_query(*, organization_id: int | None):
        query = InventoryRouteService.build_inventory_item_org_query(
            organization_id=organization_id
        )
        return query.filter(~InventoryItem.type.in_(("product", "product-reserved")))

    @staticmethod
    def list_expired_lots_for_item(*, inventory_item_id: int, today):
        return (
            InventoryLot.scoped()
            .filter(
                and_(
                    InventoryLot.inventory_item_id == inventory_item_id,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < today,
                )
            )
            .all()
        )

    @staticmethod
    def build_unified_history_query(*, inventory_item_id: int):
        return (
            UnifiedInventoryHistory.scoped()
            .filter_by(inventory_item_id=inventory_item_id)
            .options(
                joinedload(UnifiedInventoryHistory.batch),
                joinedload(UnifiedInventoryHistory.used_for_batch),
                joinedload(UnifiedInventoryHistory.affected_lot),
                joinedload(UnifiedInventoryHistory.user),
            )
        )

    @staticmethod
    def build_lots_query(*, inventory_item_id: int):
        return InventoryLot.scoped().filter_by(inventory_item_id=inventory_item_id)

    @staticmethod
    def list_expired_entries_for_item(*, inventory_item_id: int, today):
        return (
            InventoryLot.scoped()
            .filter(
                and_(
                    InventoryLot.inventory_item_id == inventory_item_id,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < today,
                )
            )
            .order_by(InventoryLot.expiration_date.asc())
            .all()
        )

    @staticmethod
    def list_ingredient_categories_ordered():
        return IngredientCategory.scoped().order_by(IngredientCategory.name).all()

    @staticmethod
    def get_ingredient_category(*, category_id: int):
        return db.session.get(IngredientCategory, category_id)

    @staticmethod
    def get_scoped_inventory_item_or_404(*, item_id: int):
        return InventoryItem.scoped().filter_by(id=item_id).first_or_404()

    @staticmethod
    def get_inventory_item_by_id_or_404_for_org(
        *, item_id: int, organization_id: int | None
    ):
        query = InventoryRouteService.build_inventory_item_org_query(
            organization_id=organization_id
        )
        return query.filter_by(id=item_id).first_or_404()

    @staticmethod
    def count_unified_history_for_item(*, inventory_item_id: int):
        return (
            UnifiedInventoryHistory.scoped()
            .filter_by(inventory_item_id=inventory_item_id)
            .count()
        )

    @staticmethod
    def list_bulk_update_inventory_records(*, organization_id: int | None, limit: int = 750):
        query = InventoryRouteService.build_inventory_item_org_query(
            organization_id=organization_id
        )
        query = query.filter(~InventoryItem.type.in_(("product", "product-reserved")))
        return (
            query.filter(not InventoryItem.is_archived)
            .order_by(InventoryItem.name.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def lot_ordering():
        return (
            case((InventoryLot.source_type == "infinite_anchor", 1), else_=0),
            InventoryLot.created_at.asc(),
        )

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
