"""Global-link drawer service boundary.

Synopsis:
Owns global-link drawer data access and linking mutations so drawer routes can
remain transport-only.
"""

from __future__ import annotations

import logging

from app.extensions import db
from app.models import GlobalItem, InventoryItem, UnifiedInventoryHistory
from app.services.global_link_suggestions import GlobalLinkSuggestionService

logger = logging.getLogger(__name__)


class GlobalLinkDrawerService:
    """Service helpers for global-link drawer route handlers."""

    @staticmethod
    def get_global_item(global_item_id: int | None) -> GlobalItem | None:
        if not global_item_id:
            return None
        return db.session.get(GlobalItem, int(global_item_id))

    @staticmethod
    def get_modal_candidates(
        *,
        global_item_id: int | None,
        organization_id: int | None,
    ) -> tuple[GlobalItem | None, list[InventoryItem]]:
        global_item = GlobalLinkDrawerService.get_global_item(global_item_id)
        if not global_item or not organization_id:
            return None, []
        items = GlobalLinkSuggestionService.find_candidates_for_global(
            global_item.id,
            organization_id,
        )
        return global_item, items

    @staticmethod
    def link_items_to_global(
        *,
        global_item: GlobalItem,
        item_ids: list[int],
        actor_user_id: int | None,
        actor_org_id: int | None,
    ) -> tuple[int, int]:
        updated = 0
        skipped = 0

        for raw_id in item_ids:
            try:
                inventory_item = db.session.get(InventoryItem, int(raw_id))
                if not inventory_item:
                    skipped += 1
                    continue

                if actor_org_id and inventory_item.organization_id != actor_org_id:
                    skipped += 1
                    continue

                if getattr(inventory_item, "global_item_id", None):
                    skipped += 1
                    continue

                if not global_item.default_unit:
                    skipped += 1
                    continue

                if not GlobalLinkSuggestionService.is_pair_compatible(
                    global_item.default_unit,
                    inventory_item.unit,
                ):
                    skipped += 1
                    continue

                old_name = inventory_item.name
                inventory_item.name = global_item.name
                if global_item.density is not None:
                    inventory_item.density = global_item.density
                inventory_item.global_item_id = global_item.id
                inventory_item.ownership = "global"

                history_event = UnifiedInventoryHistory(
                    inventory_item_id=inventory_item.id,
                    change_type="link_global",
                    quantity_change=0.0,
                    quantity_change_base=0,
                    unit=inventory_item.unit or "count",
                    notes=(
                        f"Linked to GlobalItem '{global_item.name}' "
                        f"(was '{old_name}')"
                    ),
                    created_by=actor_user_id,
                    organization_id=inventory_item.organization_id,
                )
                db.session.add(history_event)
                updated += 1
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/services/global_link_drawer_service.py:102",
                    exc_info=True,
                )
                skipped += 1
                continue

        db.session.commit()
        return updated, skipped
