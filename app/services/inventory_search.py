from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models import GlobalItem, InventoryItem
from app.models.ingredient_reference import Variation


class InventorySearchService:
    @staticmethod
    def search_inventory_items(
        *,
        query_text: str,
        inventory_type: Optional[str],
        organization_id: Optional[int],
        change_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Return suggestion payloads for the inventory modal search box."""
        normalized_query = (query_text or "").strip()
        if not organization_id or len(normalized_query) < 2:
            return []

        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 20

        normalized_type = (inventory_type or "").strip().lower() or None
        change_scope = (change_type or "").strip().lower()
        include_global = change_scope == "create"

        local_items = InventorySearchService._search_local_inventory(
            normalized_query, normalized_type, organization_id, limit
        )
        results: List[Dict] = [InventorySearchService._serialize_local(item) for item in local_items]

        if include_global and len(results) < limit:
            remaining = limit - len(results)
            global_items = InventorySearchService._search_global_items(
                normalized_query, normalized_type, remaining
            )
            results.extend(InventorySearchService._serialize_global(item) for item in global_items)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _search_local_inventory(
        query_text: str,
        inventory_type: Optional[str],
        organization_id: int,
        limit: int,
    ) -> List[InventoryItem]:
        query = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.is_archived != True,  # noqa: E712
        )
        query = query.options(
            joinedload(InventoryItem.global_item).joinedload(GlobalItem.ingredient),
            joinedload(InventoryItem.global_item)
            .joinedload(GlobalItem.variation)
            .joinedload(Variation.physical_form),
        )
        query = query.filter(~InventoryItem.type.in_(("product", "product-reserved")))
        if inventory_type:
            query = query.filter(func.lower(InventoryItem.type) == inventory_type)

        query = query.filter(InventoryItem.name.ilike(f"%{query_text}%"))
        return query.order_by(InventoryItem.name.asc()).limit(limit).all()

    @staticmethod
    def _search_global_items(
        query_text: str,
        inventory_type: Optional[str],
        limit: int,
    ) -> List[GlobalItem]:
        query = GlobalItem.query.filter(
            GlobalItem.is_archived != True,  # noqa: E712
            GlobalItem.name.ilike(f"%{query_text}%"),
        )
        if inventory_type:
            query = query.filter(func.lower(GlobalItem.item_type) == inventory_type)

        return query.order_by(GlobalItem.name.asc()).limit(limit).all()

    @staticmethod
    def _serialize_local(item: InventoryItem) -> Dict:
        payload = {
            "id": item.id,
            "text": item.name,
            "type": item.type,
            "source": "inventory",
            "unit": item.unit,
            "default_unit": item.unit,
            "global_item_id": getattr(item, "global_item_id", None),
            "default_is_perishable": bool(getattr(item, "is_perishable", False)),
            "density": item.density,
        }
        ingredient_obj = None
        variation_obj = None
        physical_form_obj = None
        if getattr(item, "global_item", None):
            ingredient_obj = getattr(item.global_item, "ingredient", None)
            variation_obj = getattr(item.global_item, "variation", None)
            if variation_obj:
                physical_form_obj = getattr(variation_obj, "physical_form", None)
        payload["ingredient_id"] = getattr(ingredient_obj, "id", None)
        payload["ingredient_name"] = (
            getattr(ingredient_obj, "name", None) or item.name
        )
        payload["variation_id"] = getattr(variation_obj, "id", None)
        payload["variation_name"] = getattr(variation_obj, "name", None)
        payload["physical_form_id"] = getattr(physical_form_obj, "id", None)
        payload["physical_form_name"] = getattr(physical_form_obj, "name", None)

        if item.type == "container":
            payload.update(
                {
                    "capacity": getattr(item, "capacity", None),
                    "capacity_unit": getattr(item, "capacity_unit", None),
                    "container_material": getattr(item, "container_material", None),
                    "container_type": getattr(item, "container_type", None),
                    "container_style": getattr(item, "container_style", None),
                    "container_color": getattr(item, "container_color", None),
                }
            )
        return payload

    @staticmethod
    def _serialize_global(item: GlobalItem) -> Dict:
        return {
            "id": item.id,
            "global_item_id": item.id,
            "text": item.name,
            "type": item.item_type,
            "source": "global",
            "unit": item.default_unit,
        }
