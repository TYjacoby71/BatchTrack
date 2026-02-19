"""Current version helpers for recipes.

Synopsis:
Marks a published recipe as the current version for its branch.

Glossary:
- Current version: Active master/variation used in production and UI.
- Branch: Master or variation line within a recipe group.
"""

from __future__ import annotations

from typing import Any, Tuple

import sqlalchemy as sa

from ...extensions import db
from ...models import Recipe


# --- Validate current ---
# Purpose: Validate that a recipe can be set as current.
def _validate_current_recipe(recipe: Recipe | None) -> Tuple[bool, str]:
    if not recipe:
        return False, "Recipe not found."
    if recipe.test_sequence is not None:
        return False, "Test versions cannot be set as current."
    if recipe.is_archived:
        return False, "Archived recipes cannot be set as current."
    if recipe.status != "published":
        return False, "Only published recipes can be set as current."
    return True, ""


# --- Clear branch current ---
# Purpose: Clear current flags for a recipe branch.
def _clear_branch_current(recipe: Recipe) -> None:
    if not recipe.recipe_group_id:
        return
    branch_query = Recipe.query.filter(
        Recipe.recipe_group_id == recipe.recipe_group_id,
        Recipe.test_sequence.is_(None),
        Recipe.is_master.is_(recipe.is_master),
    )
    if not recipe.is_master:
        branch_query = branch_query.filter(
            Recipe.variation_name == recipe.variation_name
        )
    branch_query = branch_query.filter(Recipe.id != recipe.id)
    branch_query.update({Recipe.is_current: False}, synchronize_session=False)


# --- Apply current flag ---
# Purpose: Mark a recipe as current in its branch.
def apply_current_flag(recipe: Recipe) -> None:
    _clear_branch_current(recipe)
    recipe.is_current = True


# --- Set current version ---
# Purpose: Validate and set a recipe as current.
def set_current_version(recipe_id: int) -> Tuple[bool, Any]:
    recipe = db.session.get(Recipe, recipe_id)
    ok, message = _validate_current_recipe(recipe)
    if not ok:
        return False, message
    apply_current_flag(recipe)
    db.session.commit()
    return True, recipe


# --- Ensure current versions ---
# Purpose: Ensure each branch has exactly one current version.
def ensure_current_versions_for_org(org_id: int | None) -> int:
    if not org_id:
        return 0

    db.session.flush()
    Recipe.query.filter(
        Recipe.organization_id == org_id,
        Recipe.is_current.is_(True),
        sa.or_(
            Recipe.test_sequence.isnot(None),
            Recipe.status != "published",
            Recipe.is_archived.is_(True),
        ),
    ).update({Recipe.is_current: False}, synchronize_session=False)

    candidates = (
        Recipe.query.filter(
            Recipe.organization_id == org_id,
            Recipe.test_sequence.is_(None),
            Recipe.status == "published",
            Recipe.is_archived.is_(False),
        )
        .order_by(
            Recipe.recipe_group_id.asc().nullsfirst(),
            Recipe.is_master.desc(),
            Recipe.variation_name.asc().nullsfirst(),
            Recipe.version_number.desc(),
        )
        .all()
    )

    branches: dict[tuple, list[Recipe]] = {}
    for recipe in candidates:
        if recipe.recipe_group_id is None:
            key = ("ungrouped", recipe.id)
        else:
            key = (recipe.recipe_group_id, recipe.is_master, recipe.variation_name)
        branches.setdefault(key, []).append(recipe)

    touched = 0
    for recipes in branches.values():
        current_recipes = [r for r in recipes if r.is_current]
        if len(current_recipes) == 1:
            chosen = current_recipes[0]
        elif len(current_recipes) > 1:
            chosen = max(current_recipes, key=lambda r: (r.version_number or 0))
        else:
            chosen = max(recipes, key=lambda r: (r.version_number or 0))
        for recipe in recipes:
            target = recipe.id == chosen.id
            if recipe.is_current != target:
                recipe.is_current = target
                touched += 1

    return touched


__all__ = [
    "apply_current_flag",
    "set_current_version",
    "ensure_current_versions_for_org",
]
