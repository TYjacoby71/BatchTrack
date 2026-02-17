"""Recipe form utilities (facade).

Synopsis:
Provides a stable import surface for recipe form helpers while delegating
to focused modules for parsing, templates, prefill, and variations.

Glossary:
- Facade: Thin re-export module used to keep import paths stable.
"""

from __future__ import annotations

from .form_parsing import (
    RecipeFormSubmission,
    build_draft_prompt,
    build_recipe_submission,
    coerce_float,
    collect_allowed_containers,
    ensure_portion_unit,
    extract_consumables_from_form,
    extract_ingredients_from_form,
    get_submission_status,
    parse_portioning_from_form,
    parse_service_error,
)
from .form_prefill import (
    build_prefill_from_form,
    lookup_inventory_names,
    recipe_from_form,
    safe_int,
    serialize_assoc_rows,
    serialize_prefill_rows,
)
from .form_templates import (
    get_recipe_form_data,
    is_recipe_purchase_enabled,
    is_recipe_sharing_enabled,
    render_recipe_form,
)
from .form_variations import create_variation_template

__all__ = [
    "RecipeFormSubmission",
    "build_draft_prompt",
    "build_prefill_from_form",
    "build_recipe_submission",
    "collect_allowed_containers",
    "coerce_float",
    "create_variation_template",
    "ensure_portion_unit",
    "extract_consumables_from_form",
    "extract_ingredients_from_form",
    "get_recipe_form_data",
    "get_submission_status",
    "is_recipe_purchase_enabled",
    "is_recipe_sharing_enabled",
    "lookup_inventory_names",
    "parse_portioning_from_form",
    "parse_service_error",
    "recipe_from_form",
    "render_recipe_form",
    "safe_int",
    "serialize_assoc_rows",
    "serialize_prefill_rows",
]
