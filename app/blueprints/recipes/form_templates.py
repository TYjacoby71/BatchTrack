"""Recipe form template utilities.

Synopsis:
Builds cached recipe form metadata and renders the create/edit templates.
Handles feature gating for marketplace controls and label prefix display.

Glossary:
- Form payload: Cached ingredient, category, and unit lists used by the UI.
- Label prefix display: Version-aware prefix shown on the form.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from flask import current_app, render_template, session
from flask_login import current_user

from app.models import InventoryItem
from app.models.product_category import ProductCategory
from app.models.unit import Unit
from app.services.lineage_service import format_label_prefix
from app.utils.cache_manager import app_cache
from app.utils.permissions import has_permission
from app.utils.settings import is_feature_enabled
from app.utils.unit_utils import get_global_unit_list

logger = logging.getLogger(__name__)


# --- Form cache TTL ---
# Purpose: Resolve the recipe form cache TTL from app config.
def _form_cache_ttl() -> int:
    try:
        return int(current_app.config.get("RECIPE_FORM_CACHE_TTL", 60))
    except Exception:
        return 60


# --- Serialize product category ---
# Purpose: Convert ProductCategory objects into JSON-safe payloads.
def _serialize_product_category(cat: ProductCategory) -> Dict[str, Any]:
    return {
        "id": cat.id,
        "name": cat.name,
        "is_typically_portioned": cat.is_typically_portioned,
        "skin_enabled": cat.skin_enabled,
    }


# --- Serialize inventory item ---
# Purpose: Convert InventoryItem objects into JSON-safe payloads.
def _serialize_inventory_item(
    item: InventoryItem, *, include_container_meta: bool = False
) -> Dict[str, Any]:
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


# --- Serialize unit ---
# Purpose: Convert Unit objects into JSON-safe payloads.
def _serialize_unit(unit: Unit) -> Dict[str, Any]:
    return {
        "id": unit.id,
        "name": unit.name,
        "unit_type": unit.unit_type,
        "base_unit": unit.base_unit,
        "conversion_factor": unit.conversion_factor,
        "symbol": unit.symbol,
    }


# --- Recipe form cache key ---
# Purpose: Build the cache key for recipe form data per org.
def _recipe_form_cache_key(org_id: Optional[int]) -> str:
    return f"recipes:form_data:{org_id or 'global'}"


# --- Effective org id ---
# Purpose: Resolve the current organization id for form caching.
def _effective_org_id() -> Optional[int]:
    """Resolve organization scope for recipe form inventory lists.

    - Normal users: current_user.organization_id
    - Developers: session dev_selected_org_id (to avoid cross-org leakage)
    """
    try:
        org_id = getattr(current_user, "organization_id", None)
        if org_id:
            return org_id
        if (
            getattr(current_user, "is_authenticated", False)
            and getattr(current_user, "user_type", None) == "developer"
        ):
            return session.get("dev_selected_org_id")
    except Exception:
        return None
    return None


# --- Build recipe form payload ---
# Purpose: Assemble recipe form metadata for create/edit pages.
def _build_recipe_form_payload(org_id: Optional[int]) -> Dict[str, Any]:
    # Safety: avoid cross-organization leakage if org_id cannot be resolved
    if not org_id:
        units = [
            _serialize_unit(unit)
            for unit in Unit.query.filter_by(is_active=True)
            .order_by(Unit.unit_type, Unit.name)
            .all()
        ]
        inventory_units = get_global_unit_list()
        categories = [
            _serialize_product_category(cat)
            for cat in ProductCategory.query.order_by(ProductCategory.name.asc()).all()
        ]
        return {
            "all_ingredients": [],
            "all_consumables": [],
            "all_containers": [],
            "units": units,
            "inventory_units": inventory_units,
            "product_categories": categories,
            "product_groups": [],
        }

    ingredients_query = InventoryItem.scoped().filter(InventoryItem.type == "ingredient")
    if org_id:
        ingredients_query = ingredients_query.filter_by(organization_id=org_id)
    all_ingredients = [
        _serialize_inventory_item(item)
        for item in ingredients_query.order_by(InventoryItem.name).all()
    ]

    consumables_query = InventoryItem.scoped().filter(InventoryItem.type == "consumable")
    if org_id:
        consumables_query = consumables_query.filter_by(organization_id=org_id)
    all_consumables = [
        _serialize_inventory_item(item)
        for item in consumables_query.order_by(InventoryItem.name).all()
    ]

    containers_query = InventoryItem.scoped().filter(InventoryItem.type == "container")
    if org_id:
        containers_query = containers_query.filter_by(organization_id=org_id)
    all_containers = [
        _serialize_inventory_item(item, include_container_meta=True)
        for item in containers_query.order_by(InventoryItem.name).all()
    ]

    units = [
        _serialize_unit(unit)
        for unit in Unit.query.filter_by(is_active=True)
        .order_by(Unit.unit_type, Unit.name)
        .all()
    ]
    inventory_units = get_global_unit_list()

    categories = [
        _serialize_product_category(cat)
        for cat in ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    ]

    # product_groups have been removed from the system
    product_groups = []

    return {
        "all_ingredients": all_ingredients,
        "all_consumables": all_consumables,
        "all_containers": all_containers,
        "units": units,
        "inventory_units": inventory_units,
        "product_categories": categories,
        "product_groups": product_groups,
    }


# --- Get recipe form data ---
# Purpose: Retrieve or build cached recipe form payloads.
def get_recipe_form_data():
    org_id = _effective_org_id()
    cache_key = _recipe_form_cache_key(org_id)
    cached = app_cache.get(cache_key)
    if cached is None:
        payload = _build_recipe_form_payload(org_id)
        try:
            app_cache.set(cache_key, payload, ttl=_form_cache_ttl())
        except Exception as exc:
            logger.debug("Unable to cache recipe form payload: %s", exc)
    else:
        payload = cached

    data = dict(payload)
    data["recipe_sharing_enabled"] = is_recipe_sharing_enabled()
    data["recipe_purchase_enabled"] = is_recipe_purchase_enabled()
    return data


# --- Recipe sharing enabled ---
# Purpose: Check feature flag for recipe sharing.
def is_recipe_sharing_enabled():
    if not is_feature_enabled("FEATURE_RECIPE_MARKETPLACE_LISTINGS"):
        return False
    if (
        current_user.is_authenticated
        and getattr(current_user, "user_type", "") == "developer"
    ):
        return True
    return has_permission(current_user, "recipes.sharing_controls")


# --- Recipe purchase enabled ---
# Purpose: Check feature flag for recipe purchasing.
def is_recipe_purchase_enabled():
    if not is_feature_enabled("FEATURE_RECIPE_MARKETPLACE_LISTINGS"):
        return False
    if (
        current_user.is_authenticated
        and getattr(current_user, "user_type", "") == "developer"
    ):
        return True
    return has_permission(current_user, "recipes.purchase_options")


# --- Render recipe form ---
# Purpose: Render recipe create/edit form with context data.
def render_recipe_form(recipe=None, **context):
    form_data = get_recipe_form_data()
    label_prefix_display = context.get("label_prefix_display")
    if label_prefix_display is None and recipe is not None:
        try:
            label_prefix_display = format_label_prefix(
                recipe,
                test_sequence=context.get("test_sequence_hint"),
            )
        except Exception:
            label_prefix_display = None
    payload = {**form_data, **context, "label_prefix_display": label_prefix_display}
    return render_template("pages/recipes/recipe_form.html", recipe=recipe, **payload)


__all__ = [
    "get_recipe_form_data",
    "is_recipe_purchase_enabled",
    "is_recipe_sharing_enabled",
    "render_recipe_form",
]
