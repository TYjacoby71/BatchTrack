"""Helpers for recipe line-item costing with unit conversion.

Synopsis:
Convert recipe quantities into the inventory item's pricing unit before
multiplying by ``cost_per_unit``.

Glossary:
- Recipe unit: Unit used on the recipe line (e.g., gram).
- Pricing unit: Inventory unit attached to ``cost_per_unit`` (e.g., lb).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)


def _normalized_unit(unit: Any) -> str:
    return str(unit or "").strip().lower()


def convert_quantity_to_inventory_unit(
    quantity: Any, recipe_unit: str | None, inventory_item: Any
) -> Optional[float]:
    """Convert recipe quantity into the inventory item's unit.

    Returns ``None`` when conversion fails (instead of falling back to a raw
    multiplication that can significantly overstate costs).
    """
    if inventory_item is None:
        return None

    try:
        quantity_value = float(quantity or 0.0)
    except (TypeError, ValueError):
        return None

    inventory_unit = getattr(inventory_item, "unit", None)
    if (
        not recipe_unit
        or not inventory_unit
        or _normalized_unit(recipe_unit) == _normalized_unit(inventory_unit)
    ):
        return quantity_value

    conversion_result = ConversionEngine.convert_units(
        amount=quantity_value,
        from_unit=recipe_unit,
        to_unit=inventory_unit,
        ingredient_id=getattr(inventory_item, "id", None),
        density=getattr(inventory_item, "density", None),
        rounding_decimals=None,
    )
    if (
        not conversion_result
        or not conversion_result.get("success")
        or conversion_result.get("converted_value") is None
    ):
        logger.warning(
            "Failed to convert recipe quantity for costing: item_id=%s from=%s to=%s qty=%s",
            getattr(inventory_item, "id", None),
            recipe_unit,
            inventory_unit,
            quantity_value,
        )
        return None

    try:
        return float(conversion_result["converted_value"])
    except (TypeError, ValueError):
        return None


def calculate_recipe_line_item_cost(
    quantity: Any, recipe_unit: str | None, inventory_item: Any
) -> Optional[float]:
    """Return converted line cost or ``None`` when pricing is unavailable."""
    if inventory_item is None:
        return None

    raw_cost_per_unit = getattr(inventory_item, "cost_per_unit", None)
    if raw_cost_per_unit is None:
        return None

    try:
        cost_per_unit = float(raw_cost_per_unit)
    except (TypeError, ValueError):
        return None

    quantity_in_inventory_unit = convert_quantity_to_inventory_unit(
        quantity=quantity,
        recipe_unit=recipe_unit,
        inventory_item=inventory_item,
    )
    if quantity_in_inventory_unit is None:
        return None

    return quantity_in_inventory_unit * cost_per_unit


def calculate_recipe_line_item_cost_or_zero(
    quantity: Any, recipe_unit: str | None, inventory_item: Any
) -> float:
    """Return converted line cost, defaulting to 0.0 on unavailable conversion."""
    line_cost = calculate_recipe_line_item_cost(
        quantity=quantity,
        recipe_unit=recipe_unit,
        inventory_item=inventory_item,
    )
    return float(line_cost) if line_cost is not None else 0.0
