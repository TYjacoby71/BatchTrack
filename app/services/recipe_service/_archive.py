"""Recipe archiving and listing safeguards."""
from __future__ import annotations

from typing import Tuple

from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils
from ...models import Recipe


def is_marketplace_listed(recipe: Recipe) -> bool:
    return bool(recipe.is_public) and recipe.marketplace_status == "listed"


def unlist_recipe(recipe_id: int) -> Tuple[bool, str]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        return False, "Recipe not found"
    recipe.sharing_scope = "private"
    recipe.is_public = False
    recipe.is_for_sale = False
    recipe.sale_price = None
    recipe.marketplace_status = "draft"
    db.session.commit()
    return True, "Listing removed"


def archive_recipe(recipe_id: int, *, user_id: int | None = None) -> Tuple[bool, str]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        return False, "Recipe not found"
    if is_marketplace_listed(recipe):
        return False, "Remove the marketplace listing before archiving."
    if recipe.is_archived:
        return True, "Recipe already archived."
    recipe.is_archived = True
    recipe.archived_at = TimezoneUtils.utc_now()
    recipe.archived_by = user_id
    recipe.sharing_scope = "private"
    recipe.is_public = False
    recipe.is_for_sale = False
    recipe.sale_price = None
    recipe.marketplace_status = "draft"
    db.session.commit()
    return True, "Recipe archived."


def restore_recipe(recipe_id: int) -> Tuple[bool, str]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        return False, "Recipe not found"
    if not recipe.is_archived:
        return True, "Recipe already active."
    recipe.is_archived = False
    recipe.archived_at = None
    recipe.archived_by = None
    db.session.commit()
    return True, "Recipe restored."


__all__ = [
    "archive_recipe",
    "restore_recipe",
    "unlist_recipe",
    "is_marketplace_listed",
]
