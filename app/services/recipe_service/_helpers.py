"""Shared helpers used by the recipe core service.

Synopsis:
Resolves organization context, normalizes recipe status, derives label prefixes,
and extracts structured category data from the request payload.

Glossary:
- Label prefix: Short code used in batch labels for a recipe.
- Organization scope: The tenant context used to enforce uniqueness and access.
"""

from __future__ import annotations
import logging

from typing import Any, Dict, Optional

from flask import session
from flask_login import current_user

from ...models import Recipe
from ...utils.code_generator import generate_recipe_prefix
from ._constants import _ALLOWED_RECIPE_STATUSES

logger = logging.getLogger(__name__)



# --- Resolve current org ---
# Purpose: Determine the organization id for the active user context.
def _resolve_current_org_id() -> Optional[int]:
    """Best-effort helper to determine the organization for the active user."""
    try:
        if getattr(current_user, "is_authenticated", False):
            if getattr(current_user, "user_type", None) == "developer":
                return session.get("dev_selected_org_id")
            return getattr(current_user, "organization_id", None)
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/recipe_service/_helpers.py:33", exc_info=True)
        return None
    return None


# --- Normalize status ---
# Purpose: Normalize a recipe status into a supported value.
def _normalize_status(value: str | None) -> str:
    if not value:
        return "published"
    normalized = str(value).strip().lower()
    return normalized if normalized in _ALLOWED_RECIPE_STATUSES else "published"


# --- Derive label prefix ---
# Purpose: Generate or reuse a label prefix for a recipe.
def _derive_label_prefix(
    name: str,
    requested_prefix: Optional[str],
    parent_recipe_id: Optional[int],
    parent_recipe: Optional[Recipe],
    org_id: Optional[int] = None,
) -> str:
    if requested_prefix not in (None, ""):
        return requested_prefix

    resolved_org_id = org_id
    if resolved_org_id is None and parent_recipe is not None:
        resolved_org_id = getattr(parent_recipe, "organization_id", None)
    if resolved_org_id is None:
        resolved_org_id = _resolve_current_org_id()

    final_prefix = generate_recipe_prefix(name, resolved_org_id)
    if parent_recipe_id and parent_recipe and parent_recipe.label_prefix:
        base_prefix = parent_recipe.label_prefix
        existing_variations = Recipe.query.filter(
            Recipe.parent_recipe_id == parent_recipe_id,
            Recipe.test_sequence.is_(None),
            Recipe.label_prefix.like(f"{base_prefix}%"),
        ).count()
        suffix = existing_variations + 1
        return f"{base_prefix}V{suffix}"
    return final_prefix


# --- Extract category data ---
# Purpose: Pull structured category fields from the active request.
def _extract_category_data_from_request() -> Optional[Dict[str, Any]]:
    try:
        from flask import request

        payload = request.form if request.form else None
        if not payload or not isinstance(payload, dict):
            return None
        keys = [
            "superfat_pct",
            "lye_concentration_pct",
            "lye_type",
            "soap_superfat",
            "soap_water_pct",
            "soap_lye_type",
            "fragrance_load_pct",
            "candle_fragrance_pct",
            "candle_vessel_ml",
            "vessel_fill_pct",
            "candle_fill_pct",
            "cosm_preservative_pct",
            "cosm_emulsifier_pct",
            "oil_phase_pct",
            "water_phase_pct",
            "cool_down_phase_pct",
            "base_ingredient_id",
            "moisture_loss_pct",
            "derived_pre_dry_yield_g",
            "derived_final_yield_g",
            "baker_base_flour_g",
            "herbal_ratio",
        ]
        cat_data = {}
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                cat_data[key] = value
        if "candle_fill_pct" in cat_data and "vessel_fill_pct" not in cat_data:
            cat_data["vessel_fill_pct"] = cat_data["candle_fill_pct"]
        return cat_data or None
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/recipe_service/_helpers.py:119", exc_info=True)
        return None


__all__ = [
    "_resolve_current_org_id",
    "_normalize_status",
    "_derive_label_prefix",
    "_extract_category_data_from_request",
]
