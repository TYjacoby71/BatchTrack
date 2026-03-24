"""Recipe form payload service boundary.

Synopsis:
Builds recipe form payloads (inventory, units, categories) so blueprint helper
code avoids direct query/session access.
"""

from __future__ import annotations

from typing import Any

from app.models import InventoryItem
from app.models.product_category import ProductCategory
from app.models.unit import Unit
from app.utils.unit_utils import get_global_unit_list


class RecipeFormService:
    """Service-layer helpers for recipe form metadata payloads."""

    @staticmethod
    def _serialize_product_category(cat: ProductCategory) -> dict[str, Any]:
        return {
            "id": cat.id,
            "name": cat.name,
            "is_typically_portioned": cat.is_typically_portioned,
            "skin_enabled": cat.skin_enabled,
        }

    @staticmethod
    def _serialize_inventory_item(
        item: InventoryItem, *, include_container_meta: bool = False
    ) -> dict[str, Any]:
        payload = {
            "id": item.id,
            "name": item.name,
            "unit": getattr(item, "unit", None),
            "type": getattr(item, "type", None),
        }
        if include_container_meta:
            payload.update(
                {
                    "capacity": getattr(item, "capacity", None),
                    "capacity_unit": getattr(item, "capacity_unit", None),
                    "container_display_name": getattr(
                        item, "container_display_name", item.name
                    ),
                }
            )
        return payload

    @staticmethod
    def _serialize_unit(unit: Unit) -> dict[str, Any]:
        return {
            "id": unit.id,
            "name": unit.name,
            "unit_type": unit.unit_type,
            "base_unit": unit.base_unit,
            "conversion_factor": unit.conversion_factor,
            "symbol": unit.symbol,
        }

    @classmethod
    def _list_units(cls) -> list[dict[str, Any]]:
        return [
            cls._serialize_unit(unit)
            for unit in Unit.query.filter_by(is_active=True)
            .order_by(Unit.unit_type, Unit.name)
            .all()
        ]

    @classmethod
    def _list_categories(cls) -> list[dict[str, Any]]:
        return [
            cls._serialize_product_category(cat)
            for cat in ProductCategory.query.order_by(ProductCategory.name.asc()).all()
        ]

    @classmethod
    def _list_inventory_items(
        cls,
        *,
        org_id: int | None,
        item_type: str,
        include_container_meta: bool = False,
    ) -> list[dict[str, Any]]:
        query = InventoryItem.scoped().filter(InventoryItem.type == item_type)
        if org_id:
            query = query.filter_by(organization_id=org_id)
        return [
            cls._serialize_inventory_item(
                item, include_container_meta=include_container_meta
            )
            for item in query.order_by(InventoryItem.name).all()
        ]

    @classmethod
    def build_form_payload(cls, *, org_id: int | None) -> dict[str, Any]:
        units = cls._list_units()
        inventory_units = get_global_unit_list()
        categories = cls._list_categories()

        if not org_id:
            return {
                "all_ingredients": [],
                "all_consumables": [],
                "all_containers": [],
                "units": units,
                "inventory_units": inventory_units,
                "product_categories": categories,
                "product_groups": [],
            }

        all_ingredients = cls._list_inventory_items(org_id=org_id, item_type="ingredient")
        all_consumables = cls._list_inventory_items(org_id=org_id, item_type="consumable")
        all_containers = cls._list_inventory_items(
            org_id=org_id,
            item_type="container",
            include_container_meta=True,
        )

        return {
            "all_ingredients": all_ingredients,
            "all_consumables": all_consumables,
            "all_containers": all_containers,
            "units": units,
            "inventory_units": inventory_units,
            "product_categories": categories,
            "product_groups": [],
        }
