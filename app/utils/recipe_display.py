"""Recipe display helpers.

Synopsis:
Provide consistent, lineage-aware recipe names for UI and DTOs.
"""

from __future__ import annotations

from typing import Any


def format_recipe_lineage_name(recipe: Any, include_test_number: bool = False) -> str:
    """Return a lineage-aware recipe display name.

    Rules:
    - Masters: "Master Name"
    - Master tests: "Master Name - Test" (optionally include number)
    - Variations: "Master Name - Variation Name"
    - Variation tests: "Master Name - Variation Name Test"
    """
    if not recipe:
        return ""

    base_master = None
    group = getattr(recipe, "recipe_group", None)
    if group and getattr(group, "name", None):
        base_master = group.name

    if not base_master:
        if getattr(recipe, "is_master", False):
            base_master = getattr(recipe, "name", None)
        else:
            parent_master = getattr(recipe, "parent_master", None)
            base_master = getattr(parent_master, "name", None) or getattr(
                recipe, "name", None
            )

    base_master = (base_master or "").strip()

    variation_name = None
    if not getattr(recipe, "is_master", False):
        variation_name = getattr(recipe, "variation_name", None) or getattr(
            recipe, "name", None
        )
        variation_name = (variation_name or "").strip()
        if not variation_name or variation_name == base_master:
            variation_name = None

    if variation_name:
        display = f"{base_master} - {variation_name}" if base_master else variation_name
    else:
        display = base_master or ""

    test_sequence = getattr(recipe, "test_sequence", None)
    if test_sequence:
        if variation_name:
            display = f"{display} Test"
        else:
            display = f"{display} - Test" if display else "Test"
        if include_test_number:
            display = f"{display} {test_sequence}"

    return display or getattr(recipe, "name", "") or "Recipe"
