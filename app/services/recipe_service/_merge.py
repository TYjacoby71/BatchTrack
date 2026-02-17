"""Helpers for re-basing recipe variations onto new masters.

Synopsis:
Compute ingredient deltas to rebase a variation on a new master.

Glossary:
- Delta: Ingredient differences between two recipe versions.
- Rebase: Apply deltas from old master to a new master.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from ...models import Recipe


# --- Ingredient map ---
# Purpose: Build a map of ingredient quantities by item.
def _ingredient_map(rows: Iterable) -> Dict[int, Dict[str, float | str]]:
    mapping: Dict[int, Dict[str, float | str]] = {}
    for row in rows or []:
        item_id = getattr(row, "inventory_item_id", None) or row.get(
            "inventory_item_id"
        )
        quantity = getattr(row, "quantity", None) or row.get("quantity")
        unit = getattr(row, "unit", None) or row.get("unit")
        if item_id is None:
            continue
        try:
            qty = float(quantity or 0)
        except Exception:
            qty = 0.0
        mapping[int(item_id)] = {"quantity": qty, "unit": unit}
    return mapping


# --- Build ingredient delta ---
# Purpose: Build delta rows between variation and base.
def _build_delta(
    variation_map: Dict[int, Dict[str, float | str]],
    base_map: Dict[int, Dict[str, float | str]],
) -> Dict[int, Dict[str, float | str]]:
    delta: Dict[int, Dict[str, float | str]] = {}
    for item_id, payload in variation_map.items():
        base_payload = base_map.get(item_id)
        base_qty = float(base_payload["quantity"]) if base_payload else 0.0
        delta_qty = float(payload["quantity"]) - base_qty
        if abs(delta_qty) < 1e-9:
            continue
        delta[item_id] = {"quantity": delta_qty, "unit": payload.get("unit")}
    return delta


# --- Rebase variation ---
# Purpose: Rebase a variation onto a new master.
def build_rebased_ingredients(
    variation: Recipe,
    old_master: Recipe,
    new_master: Recipe,
) -> Tuple[List[Dict[str, float | str]], List[int]]:
    """Return merged ingredient rows and overlap item ids for UI hints."""
    variation_map = _ingredient_map(getattr(variation, "recipe_ingredients", []))
    old_master_map = _ingredient_map(getattr(old_master, "recipe_ingredients", []))
    new_master_map = _ingredient_map(getattr(new_master, "recipe_ingredients", []))

    delta_map = _build_delta(variation_map, old_master_map)
    merged_map = {
        item_id: payload.copy() for item_id, payload in new_master_map.items()
    }
    overlap_ids: List[int] = []

    for item_id, payload in delta_map.items():
        delta_qty = float(payload["quantity"])
        if item_id in merged_map:
            merged_map[item_id]["quantity"] = (
                float(merged_map[item_id]["quantity"]) + delta_qty
            )
            overlap_ids.append(item_id)
        else:
            if delta_qty < 0:
                continue
            merged_map[item_id] = payload.copy()

    merged_rows: List[Dict[str, float | str]] = []
    for item_id, payload in merged_map.items():
        qty = float(payload.get("quantity") or 0)
        if qty <= 0:
            continue
        merged_rows.append(
            {
                "inventory_item_id": item_id,
                "quantity": qty,
                "unit": payload.get("unit"),
            }
        )

    return merged_rows, overlap_ids


__all__ = ["build_rebased_ingredients"]
