"""Subscription downgrade helpers for recipe limits.

Synopsis:
Handles downgrade selection, archiving, and restore-on-upgrade rules.

Glossary:
- Downgrade selection: User-selected recipes to keep active.
- Archive: Soft-hide recipes beyond tier limits.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from app.extensions import db
from app.models import Recipe
from app.utils.timezone_utils import TimezoneUtils


# --- Listing lock check ---
# Purpose: Check if a recipe is locked by listing.
def _recipe_listing_locked(recipe: Recipe) -> bool:
    return bool(recipe.is_public) and recipe.marketplace_status == "listed"


# --- Tier recipe limit ---
# Purpose: Resolve recipe limit for a tier.
def _recipe_limit_for_tier(tier) -> int | None:
    if not tier:
        return None
    limit = getattr(tier, "max_recipes", None)
    if limit is None or int(limit) < 0:
        return None
    return int(limit)


# --- Active recipe fetch ---
# Purpose: Fetch active recipes for an organization.
def fetch_active_recipes(org_id: int) -> List[Recipe]:
    return (
        Recipe.query.filter(
            Recipe.organization_id == org_id,
            Recipe.is_archived.is_(False),
        )
        .order_by(Recipe.updated_at.desc())
        .all()
    )


# --- Downgrade context ---
# Purpose: Build downgrade UI context for a target tier.
def build_downgrade_context(org, tier) -> Dict[str, object]:
    limit = _recipe_limit_for_tier(tier)
    active_recipes = fetch_active_recipes(org.id)
    required_count = min(limit, len(active_recipes)) if limit is not None else 0
    locked_ids = [r.id for r in active_recipes if _recipe_listing_locked(r)]
    return {
        "limit": limit,
        "required_count": required_count,
        "active_recipes": active_recipes,
        "locked_ids": locked_ids,
    }


# --- Apply downgrade selection ---
# Purpose: Apply downgrade selections and archive remainder.
def apply_downgrade_selection(org, tier, keep_ids: List[int], user_id: int | None = None) -> Tuple[bool, str]:
    limit = _recipe_limit_for_tier(tier)
    if limit is None:
        return True, "No recipe limit for this tier."

    active_recipes = fetch_active_recipes(org.id)
    total_active = len(active_recipes)
    required_count = min(limit, total_active)

    keep_set = {int(rid) for rid in keep_ids}
    locked_ids = {r.id for r in active_recipes if _recipe_listing_locked(r)}

    if locked_ids - keep_set:
        return False, "Remove marketplace listings or keep all listed recipes active."

    if total_active > limit and len(keep_set) != required_count:
        return False, f"Please select exactly {required_count} recipes to keep."
    if total_active <= limit and len(keep_set) != total_active:
        return False, f"Please keep all {total_active} recipes active for this tier."

    now = TimezoneUtils.utc_now()
    for recipe in active_recipes:
        if recipe.id in keep_set:
            continue
        if _recipe_listing_locked(recipe):
            return False, f"Recipe {recipe.name} is listed and cannot be archived."
        recipe.is_archived = True
        recipe.archived_at = now
        recipe.archived_by = user_id
        recipe.sharing_scope = "private"
        recipe.is_public = False
        recipe.is_for_sale = False
        recipe.sale_price = None
        recipe.marketplace_status = "draft"

    db.session.commit()
    return True, "Recipes archived for downgrade."


# --- Restore archived recipes ---
# Purpose: Restore archived recipes up to tier limits.
def restore_archived_for_tier(org, tier) -> int:
    limit = _recipe_limit_for_tier(tier)
    if limit is None:
        to_restore = (
            Recipe.query.filter(
                Recipe.organization_id == org.id,
                Recipe.is_archived.is_(True),
            )
            .order_by(Recipe.archived_at.asc())
            .all()
        )
    else:
        active_count = Recipe.query.filter(
            Recipe.organization_id == org.id,
            Recipe.is_archived.is_(False),
        ).count()
        remaining = max(0, limit - active_count)
        if remaining <= 0:
            return 0
        to_restore = (
            Recipe.query.filter(
                Recipe.organization_id == org.id,
                Recipe.is_archived.is_(True),
            )
            .order_by(Recipe.archived_at.asc())
            .limit(remaining)
            .all()
        )

    restored = 0
    for recipe in to_restore:
        recipe.is_archived = False
        recipe.archived_at = None
        recipe.archived_by = None
        restored += 1
    if restored:
        db.session.commit()
    return restored


__all__ = [
    "build_downgrade_context",
    "apply_downgrade_selection",
    "restore_archived_for_tier",
]
