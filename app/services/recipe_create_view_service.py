"""Recipe-create route service boundary.

Synopsis:
Encapsulates data-access helpers used by recipe create/edit/import routes so
controllers stay transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import InventoryItem, Recipe
from app.models.product_category import ProductCategory


class RecipeCreateViewService:
    """Data-access helpers for recipe create route workflows."""

    @staticmethod
    def list_purchased_recipes_for_org(organization_id: int | None) -> list[Recipe]:
        if not organization_id:
            return []
        return (
            Recipe.scoped()
            .options(joinedload(Recipe.recipe_ingredients))
            .filter(
                Recipe.organization_id == organization_id,
                Recipe.org_origin_purchased.is_(True),
                Recipe.test_sequence.is_(None),
            )
            .all()
        )

    @staticmethod
    def collect_new_inventory_item_names_from_submission(
        submitted_ingredients: list[dict[str, Any]],
    ) -> list[str]:
        names: list[str] = []
        for ingredient in submitted_ingredients or []:
            item_id = ingredient.get("item_id")
            if not item_id:
                continue
            item = db.session.get(InventoryItem, item_id)
            if (
                item
                and not getattr(item, "global_item_id", None)
                and float(getattr(item, "quantity", 0) or 0) == 0.0
            ):
                names.append(item.name)
        return names

    @staticmethod
    def find_product_category_id_by_name(category_name: str | None) -> int | None:
        clean_name = (category_name or "").strip()
        if not clean_name:
            return None
        category = ProductCategory.query.filter(
            func.lower(ProductCategory.name) == func.lower(db.literal(clean_name))
        ).first()
        return category.id if category else None

    @staticmethod
    def get_recipe_by_id(recipe_id: int | None) -> Recipe | None:
        if not recipe_id:
            return None
        return db.session.get(Recipe, recipe_id)

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
