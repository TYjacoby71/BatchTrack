"""Recipe form prefill utilities.

Synopsis:
Builds prefill payloads for ingredients and consumables and maps form fields
back onto Recipe objects. Provides shared coercion helpers for form inputs.

Glossary:
- Prefill: Serialized form state for ingredients and consumables.
- Association rows: Ingredient or consumable payloads for templates.
"""

from __future__ import annotations

from itertools import zip_longest

from app.models import InventoryItem, Recipe


# --- Recipe from form ---
# Purpose: Map submitted form fields onto a Recipe object.
def recipe_from_form(form, base_recipe=None):
    recipe = Recipe()
    recipe.name = form.get("name") or (base_recipe.name if base_recipe else "")
    recipe.instructions = form.get("instructions") or (
        base_recipe.instructions if base_recipe else ""
    )
    recipe.label_prefix = form.get("label_prefix") or (
        base_recipe.label_prefix if base_recipe else ""
    )
    recipe.category_id = safe_int(form.get("category_id")) or (
        base_recipe.category_id if base_recipe else None
    )
    recipe.parent_recipe_id = (
        base_recipe.parent_recipe_id
        if base_recipe and getattr(base_recipe, "parent_recipe_id", None)
        else None
    )

    product_store_url = form.get("product_store_url")
    if product_store_url is not None:
        recipe.product_store_url = product_store_url.strip() or None

    # product_group_id has been removed from the system

    try:
        if form.get("predicted_yield") not in (None, ""):
            recipe.predicted_yield = float(form.get("predicted_yield"))
        else:
            recipe.predicted_yield = (
                base_recipe.predicted_yield if base_recipe else None
            )
    except (TypeError, ValueError):
        recipe.predicted_yield = base_recipe.predicted_yield if base_recipe else None
    recipe.predicted_yield_unit = form.get("predicted_yield_unit") or (
        base_recipe.predicted_yield_unit if base_recipe else ""
    )

    recipe.allowed_containers = [
        int(identifier)
        for identifier in form.getlist("allowed_containers[]")
        if identifier
    ] or (
        list(base_recipe.allowed_containers)
        if base_recipe and base_recipe.allowed_containers
        else []
    )

    is_portioned = form.get("is_portioned") == "true"
    recipe.is_portioned = is_portioned or (
        base_recipe.is_portioned if base_recipe else False
    )
    recipe.portion_name = form.get("portion_name") or (
        base_recipe.portion_name if base_recipe else None
    )
    try:
        if form.get("portion_count"):
            recipe.portion_count = int(form.get("portion_count"))
        else:
            recipe.portion_count = base_recipe.portion_count if base_recipe else None
    except (TypeError, ValueError):
        recipe.portion_count = base_recipe.portion_count if base_recipe else None
    recipe.portioning_data = (
        {
            "is_portioned": recipe.is_portioned,
            "portion_name": recipe.portion_name,
            "portion_count": recipe.portion_count,
        }
        if recipe.is_portioned
        else None
    )

    return recipe


# --- Build prefill ---
# Purpose: Build prefill payloads from raw form data.
def build_prefill_from_form(form):
    ingredient_ids = [safe_int(val) for val in form.getlist("ingredient_ids[]")]
    amounts = form.getlist("amounts[]")
    units = form.getlist("units[]")
    global_ids = [safe_int(val) for val in form.getlist("global_item_ids[]")]

    consumable_ids = [safe_int(val) for val in form.getlist("consumable_ids[]")]
    consumable_amounts = form.getlist("consumable_amounts[]")
    consumable_units = form.getlist("consumable_units[]")

    lookup_ids = [
        identifier for identifier in ingredient_ids + consumable_ids if identifier
    ]
    name_lookup = lookup_inventory_names(lookup_ids)

    ingredient_rows = []
    for ing_id, gi_id, amt, unit in zip_longest(
        ingredient_ids, global_ids, amounts, units, fillvalue=None
    ):
        if not any([ing_id, gi_id, amt, unit]):
            continue
        ingredient_rows.append(
            {
                "inventory_item_id": ing_id,
                "global_item_id": gi_id,
                "quantity": amt,
                "unit": unit,
                "name": name_lookup.get(ing_id, ""),
            }
        )

    consumable_rows = []
    for cid, amt, unit in zip_longest(
        consumable_ids, consumable_amounts, consumable_units, fillvalue=None
    ):
        if not any([cid, amt, unit]):
            continue
        consumable_rows.append(
            {
                "inventory_item_id": cid,
                "quantity": amt,
                "unit": unit,
                "name": name_lookup.get(cid, ""),
            }
        )

    return ingredient_rows, consumable_rows


# --- Serialize prefill rows ---
# Purpose: Normalize prefill rows for JSON serialization.
def serialize_prefill_rows(rows):
    ids = [row.get("item_id") for row in rows if row.get("item_id")]
    name_lookup = lookup_inventory_names(ids)
    serialized = []
    for row in rows:
        item_id = row.get("item_id")
        serialized.append(
            {
                "inventory_item_id": item_id,
                "global_item_id": row.get("global_item_id"),
                "quantity": row.get("quantity"),
                "unit": row.get("unit"),
                "name": row.get("name") or name_lookup.get(item_id, ""),
            }
        )
    return serialized


# --- Serialize association rows ---
# Purpose: Normalize association rows for JSON serialization.
def serialize_assoc_rows(associations):
    serialized = []
    for assoc in associations:
        serialized.append(
            {
                "inventory_item_id": assoc.inventory_item_id,
                "quantity": assoc.quantity,
                "unit": assoc.unit,
                "name": assoc.inventory_item.name if assoc.inventory_item else "",
            }
        )
    return serialized


# --- Lookup inventory names ---
# Purpose: Resolve inventory item names for UI display.
def lookup_inventory_names(item_ids):
    if not item_ids:
        return {}
    unique_ids = list({item_id for item_id in item_ids if item_id})
    if not unique_ids:
        return {}
    items = InventoryItem.scoped().filter(InventoryItem.id.in_(unique_ids)).all()
    return {item.id: item.name for item in items}


# --- Safe int ---
# Purpose: Coerce values into integers with guardrails.
def safe_int(value):
    try:
        return int(value) if value not in (None, "", []) else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "build_prefill_from_form",
    "lookup_inventory_names",
    "recipe_from_form",
    "safe_int",
    "serialize_assoc_rows",
    "serialize_prefill_rows",
]
