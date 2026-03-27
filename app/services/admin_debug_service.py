"""Admin debug service boundary.

Synopsis:
Provides organization-scoped FIFO validation lookups so admin debug routes can
avoid direct model queries.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.models import InventoryItem


class AdminDebugService:
    """Service helpers for admin debug FIFO validation endpoints."""

    @staticmethod
    def list_inventory_items_for_org(
        organization_id: int | None,
    ) -> list[InventoryItem]:
        return InventoryItem.query.filter_by(organization_id=organization_id).all()

    @staticmethod
    def get_inventory_item_for_org(
        *,
        item_id: int,
        organization_id: int | None,
    ) -> InventoryItem | None:
        return InventoryItem.query.filter_by(
            id=item_id,
            organization_id=organization_id,
        ).first()
