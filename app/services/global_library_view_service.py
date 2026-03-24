"""Global library view service boundary.

Synopsis:
Encapsulates global-library detail/save/stats data lookups so
`global_library/routes.py` stays transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import GlobalItem, InventoryItem


class GlobalLibraryViewService:
    """Service helpers for global-library route data access."""

    @staticmethod
    def get_active_global_item_or_404(item_id: int) -> GlobalItem:
        return (
            GlobalItem.query.filter(
                GlobalItem.is_archived.is_(False),
                GlobalItem.id == item_id,
            ).first_or_404()
        )

    @staticmethod
    def get_global_item_or_404(item_id: int) -> GlobalItem:
        return db.get_or_404(GlobalItem, item_id)

    @staticmethod
    def list_related_items_for_detail(
        source_item: GlobalItem,
        *,
        limit: int = 6,
    ) -> list[GlobalItem]:
        return GlobalLibraryViewService.list_related_active_items(
            source_item=source_item,
            limit=limit,
        )

    @staticmethod
    def list_related_active_items(
        *,
        source_item: GlobalItem,
        limit: int = 6,
    ) -> list[GlobalItem]:
        query = (
            GlobalItem.query.filter(
                GlobalItem.item_type == source_item.item_type,
                GlobalItem.id != source_item.id,
                GlobalItem.is_archived.is_(False),
            )
            .order_by(GlobalItem.name.asc())
            .limit(limit)
        )
        if source_item.ingredient_category_id:
            query = query.filter(
                GlobalItem.ingredient_category_id == source_item.ingredient_category_id
            )
        return query.all()

    @staticmethod
    def find_existing_inventory_item_for_org(
        *,
        organization_id: int | None,
        global_item_id: int,
    ) -> InventoryItem | None:
        return GlobalLibraryViewService.find_existing_inventory_link(
            organization_id=organization_id,
            global_item_id=global_item_id,
        )

    @staticmethod
    def find_existing_inventory_link(
        *,
        organization_id: int | None,
        global_item_id: int,
    ) -> InventoryItem | None:
        if not organization_id:
            return None
        return (
            InventoryItem.query.filter(
                InventoryItem.organization_id == organization_id,
                InventoryItem.global_item_id == global_item_id,
                InventoryItem.is_archived.is_(False),
            ).first()
        )
