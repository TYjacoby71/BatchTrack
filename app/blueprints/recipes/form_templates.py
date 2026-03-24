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

from app.services.lineage_service import format_label_prefix
from app.services.recipe_form_service import RecipeFormService
from app.utils.cache_manager import app_cache
from app.utils.permissions import has_permission
from app.utils.settings import is_feature_enabled

logger = logging.getLogger(__name__)


# --- Form cache TTL ---
# Purpose: Resolve the recipe form cache TTL from app config.
def _form_cache_ttl() -> int:
    try:
        return int(current_app.config.get("RECIPE_FORM_CACHE_TTL", 60))
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/recipes/form_templates.py:37",
            exc_info=True,
        )
        return 60


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
        logger.warning(
            "Suppressed exception fallback at app/blueprints/recipes/form_templates.py:112",
            exc_info=True,
        )
        return None
    return None


# --- Build recipe form payload ---
# Purpose: Assemble recipe form metadata for create/edit pages.
def _build_recipe_form_payload(org_id: Optional[int]) -> Dict[str, Any]:
    return RecipeFormService.build_form_payload(org_id=org_id)


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
            logger.warning(
                "Suppressed exception fallback at app/blueprints/recipes/form_templates.py:252",
                exc_info=True,
            )
            label_prefix_display = None
    payload = {**form_data, **context, "label_prefix_display": label_prefix_display}
    return render_template("pages/recipes/recipe_form.html", recipe=recipe, **payload)


__all__ = [
    "get_recipe_form_data",
    "is_recipe_purchase_enabled",
    "is_recipe_sharing_enabled",
    "render_recipe_form",
]
