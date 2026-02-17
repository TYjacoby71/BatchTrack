"""Portioning helpers for recipe core."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ...models import Recipe


def _clear_portioning(recipe: Recipe) -> None:
    recipe.portioning_data = None
    recipe.is_portioned = False
    recipe.portion_name = None
    recipe.portion_count = None
    recipe.portion_unit_id = None


def _apply_portioning_settings(
    recipe: Recipe,
    *,
    portioning_data: Optional[Dict[str, Any]],
    is_portioned: Optional[bool],
    portion_name: Optional[str],
    portion_count: Optional[int],
    portion_unit_id: Optional[int],
    allow_partial: bool,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    def _missing_count_error() -> Dict[str, Any]:
        return {
            "message": "For portioned recipes, portion count must be provided.",
            "error": "For portioned recipes, portion count must be provided.",
            "missing_fields": ["portion count"],
        }

    if portioning_data is not None:
        wants_portioning = bool(portioning_data and portioning_data.get("is_portioned"))
        if wants_portioning:
            candidate = portioning_data.get("portion_count")
            try:
                resolved_count = int(candidate) if candidate is not None else 0
            except (TypeError, ValueError):
                resolved_count = 0

            if resolved_count <= 0:
                if allow_partial:
                    resolved_count = None
                else:
                    return False, _missing_count_error()

            recipe.portioning_data = dict(portioning_data)
            recipe.is_portioned = True
            recipe.portion_name = portioning_data.get("portion_name")
            recipe.portion_count = resolved_count
            recipe.portion_unit_id = portioning_data.get("portion_unit_id")
        else:
            _clear_portioning(recipe)

    if is_portioned is not None:
        recipe.is_portioned = bool(is_portioned)
        if not recipe.is_portioned:
            _clear_portioning(recipe)

    if portion_name is not None:
        recipe.portion_name = portion_name
    if portion_count is not None:
        recipe.portion_count = portion_count
    if portion_unit_id is not None:
        recipe.portion_unit_id = portion_unit_id

    if not recipe.is_portioned:
        _clear_portioning(recipe)

    return True, None


__all__ = [
    "_apply_portioning_settings",
]
