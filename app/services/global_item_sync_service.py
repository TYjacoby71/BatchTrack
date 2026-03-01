"""Global item synchronization service.

Synopsis:
Sync linked inventory items with updates to global catalog entries.

Glossary:
- Global item: Canonical ingredient entry in the global catalog.
- Ownership: Flag indicating whether an item is globally managed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.extensions import db
from app.models import GlobalItem, InventoryItem, UnifiedInventoryHistory

logger = logging.getLogger(__name__)


# --- Global item sync ---
# Purpose: Sync linked inventory items to global item updates.
class GlobalItemSyncService:
    """Keep org inventory items in sync with their linked GlobalItem.

    Core rules:
    - Only sync items that are *linked* (global_item_id matches AND ownership == 'global').
    - Never overwrite a user's chosen inventory unit if they intentionally use a different unit.
      (We only update unit when it still matches the previous global default or is blank.)
    - For other fields, update only when the current value still matches the prior global value
      (or is blank), so we don't clobber org customizations.
    """

    @staticmethod
    def _maybe_update_value(
        obj: Any,
        attr: str,
        *,
        new_value: Any,
        old_value: Any = None,
        allow_overwrite_if_matches_old: bool = True,
        allow_overwrite_if_empty: bool = True,
    ) -> bool:
        current = getattr(obj, attr, None)
        should_overwrite = False

        if allow_overwrite_if_empty and (
            current is None or current == "" or current == []
        ):
            should_overwrite = True
        elif allow_overwrite_if_matches_old and current == old_value:
            should_overwrite = True

        if should_overwrite:
            setattr(obj, attr, new_value)
            return True
        return False

    @classmethod
    def sync_linked_inventory_items(
        cls, global_item: GlobalItem, *, before: Dict[str, Any] | None = None
    ) -> int:
        """Apply changes from a global item edit to linked inventory items.

        Args:
            global_item: the (already-mutated) GlobalItem instance
            before: snapshot of the GlobalItem fields before mutation (old values)

        Returns:
            Number of inventory items updated.
        """
        before = before or {}

        linked_items = InventoryItem.query.filter(
            InventoryItem.global_item_id == global_item.id,
            InventoryItem.is_archived.is_(False),
            InventoryItem.organization_id.isnot(None),
            InventoryItem.ownership == "global",
        ).all()

        updated_count = 0

        for inv in linked_items:
            changed = False

            # Name: always sync for linked items
            if inv.name != global_item.name:
                inv.name = global_item.name
                changed = True

            # Inventory unit: never override a user's chosen unit if they diverged.
            # Only update if it still matches the *previous* global default (or is blank).
            if inv.type != "container":
                old_default_unit = before.get("default_unit")
                new_default_unit = getattr(global_item, "default_unit", None)
                if new_default_unit:
                    if cls._maybe_update_value(
                        inv,
                        "unit",
                        new_value=new_default_unit,
                        old_value=old_default_unit,
                        allow_overwrite_if_matches_old=True,
                        allow_overwrite_if_empty=True,
                    ):
                        changed = True

            # Ingredient density: update if it still matches old global density or is unset
            if inv.type == "ingredient":
                if global_item.density is not None:
                    if cls._maybe_update_value(
                        inv,
                        "density",
                        new_value=global_item.density,
                        old_value=before.get("density"),
                        allow_overwrite_if_matches_old=True,
                        allow_overwrite_if_empty=True,
                    ):
                        changed = True

                # Sync selected ingredient metadata fields (only if they still match the previous global values)
                meta_fields = [
                    "saponification_value",
                    "iodine_value",
                    "melting_point_c",
                    "flash_point_c",
                    "ph_value",
                    "moisture_content_percent",
                    "comedogenic_rating",
                    "recommended_fragrance_load_pct",
                    "inci_name",
                    "cas_number",
                    "protein_content_pct",
                    "brewing_color_srm",
                    "brewing_potential_sg",
                    "brewing_diastatic_power_lintner",
                    "fatty_acid_profile",
                    "certifications",
                ]
                for field in meta_fields:
                    if cls._maybe_update_value(
                        inv,
                        field,
                        new_value=getattr(global_item, field, None),
                        old_value=before.get(field),
                        allow_overwrite_if_matches_old=True,
                        allow_overwrite_if_empty=True,
                    ):
                        changed = True

            # Container/packaging metadata: capacity + capacity_unit + structured attributes
            if inv.type in ("container", "packaging"):
                for field in [
                    "capacity",
                    "capacity_unit",
                    "container_material",
                    "container_type",
                    "container_style",
                    "container_color",
                ]:
                    if cls._maybe_update_value(
                        inv,
                        field,
                        new_value=getattr(global_item, field, None),
                        old_value=before.get(field),
                        allow_overwrite_if_matches_old=True,
                        allow_overwrite_if_empty=True,
                    ):
                        changed = True

            if changed:
                updated_count += 1
                try:
                    db.session.add(
                        UnifiedInventoryHistory(
                            inventory_item_id=inv.id,
                            change_type="sync_global",
                            quantity_change=0.0,
                            quantity_change_base=0,
                            unit=inv.unit or "count",
                            notes=f"Synced fields from GlobalItem '{global_item.name}'",
                            created_by=None,
                            organization_id=inv.organization_id,
                        )
                    )
                except Exception:
                    # History is best-effort; don't break sync.
                    logger.warning("Suppressed exception fallback at app/services/global_item_sync_service.py:186", exc_info=True)
                    pass

        logger.info(
            "GlobalItemSyncService: synced %s linked inventory items for global_item_id=%s",
            updated_count,
            global_item.id,
        )
        return updated_count

    @classmethod
    def relink_inventory_item(cls, inv: InventoryItem, global_item: GlobalItem) -> None:
        """Relink a single inventory item and pull global properties back in.

        We always restore global properties (density, container specs, etc.) on relink,
        but we *never* override the inventory unit if the user has chosen a different unit.
        """
        inv.ownership = "global"
        inv.global_item_id = global_item.id

        inv.name = global_item.name

        # Preserve user's unit if they differ from global default.
        if inv.type != "container":
            if global_item.default_unit and (
                not inv.unit or inv.unit == global_item.default_unit
            ):
                inv.unit = global_item.default_unit

        if inv.type == "ingredient":
            if global_item.density is not None:
                inv.density = global_item.density
            for field in [
                "saponification_value",
                "iodine_value",
                "melting_point_c",
                "flash_point_c",
                "ph_value",
                "moisture_content_percent",
                "comedogenic_rating",
                "recommended_fragrance_load_pct",
                "inci_name",
                "cas_number",
                "protein_content_pct",
                "brewing_color_srm",
                "brewing_potential_sg",
                "brewing_diastatic_power_lintner",
                "fatty_acid_profile",
                "certifications",
            ]:
                setattr(inv, field, getattr(global_item, field, None))

        if inv.type in ("container", "packaging"):
            for field in [
                "capacity",
                "capacity_unit",
                "container_material",
                "container_type",
                "container_style",
                "container_color",
            ]:
                setattr(inv, field, getattr(global_item, field, None))
