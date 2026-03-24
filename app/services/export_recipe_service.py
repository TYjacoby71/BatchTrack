"""Export recipe lookup service boundary.

Synopsis:
Provides recipe resolution and ownership normalization for export routes so
controller code avoids direct session/query access.
"""

from __future__ import annotations

from flask import abort

from app.extensions import db
from app.models import Recipe


class ExportRecipeService:
    """Service helpers for export route recipe lookup and ownership updates."""

    @staticmethod
    def get_recipe_or_abort(
        *,
        recipe_id: int,
        user_organization_id: int | None,
    ) -> Recipe:
        recipe = db.session.get(Recipe, recipe_id)
        if recipe is None:
            abort(404)
        if user_organization_id and recipe.organization_id != user_organization_id:
            abort(403)
        return recipe

    @staticmethod
    def ensure_org_origin_published(recipe: Recipe) -> None:
        updated = False
        if recipe.org_origin_recipe_id != recipe.id:
            recipe.org_origin_recipe_id = recipe.id
            updated = True
        if recipe.org_origin_type in (None, "authored"):
            recipe.org_origin_type = "published"
            updated = True
        if updated:
            db.session.commit()
