"""Recipe-manage route service boundary.

Synopsis:
Encapsulates recipe-manage route data/session access so
`recipes/views/manage_routes.py` stays transport-focused.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Recipe, RecipeIngredient, RecipeLineage
from app.utils.notes import append_timestamped_note


class RecipeManageViewService:
    """Data/session helpers for recipe management route workflows."""

    @staticmethod
    def list_group_variations_for_masters(
        *,
        recipes: list[Recipe],
        organization_id: int | None,
    ) -> dict[int, list[Recipe]]:
        group_ids = sorted(
            {
                int(recipe.recipe_group_id)
                for recipe in recipes
                if getattr(recipe, "recipe_group_id", None)
            }
        )
        if not group_ids:
            return {}

        query = Recipe.scoped().filter(
            Recipe.recipe_group_id.in_(group_ids),
            Recipe.is_master.is_(False),
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
        )
        if organization_id:
            query = query.filter(Recipe.organization_id == organization_id)

        grouped: dict[int, list[Recipe]] = {}
        for variation in query.order_by(
            Recipe.recipe_group_id.asc(),
            Recipe.variation_name.asc().nullsfirst(),
            Recipe.version_number.desc(),
        ).all():
            grouped.setdefault(int(variation.recipe_group_id), []).append(variation)
        return grouped

    @staticmethod
    def paginate_master_recipes(
        *,
        organization_id: int | None,
        page: int,
        per_page: int,
    ):
        ingredient_counts_query = db.session.query(
            RecipeIngredient.recipe_id.label("recipe_id"),
            func.count(RecipeIngredient.id).label("ingredient_count"),
        ).group_by(RecipeIngredient.recipe_id)
        if organization_id:
            ingredient_counts_query = ingredient_counts_query.filter(
                RecipeIngredient.organization_id == organization_id
            )

        ingredient_counts = ingredient_counts_query.subquery()

        base_filters = [
            Recipe.parent_recipe_id.is_(None),
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
        ]
        if organization_id:
            base_filters.append(Recipe.organization_id == organization_id)

        query = (
            Recipe.scoped()
            .filter(*base_filters)
            .outerjoin(ingredient_counts, ingredient_counts.c.recipe_id == Recipe.id)
            .add_columns(ingredient_counts.c.ingredient_count)
        )
        return (
            query.options(selectinload(Recipe.variations))
            .order_by(Recipe.name.asc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    @staticmethod
    def count_active_variations_for_recipe(*, recipe: Recipe) -> int:
        if recipe.recipe_group_id:
            return (
                Recipe.scoped()
                .filter(
                    Recipe.recipe_group_id == recipe.recipe_group_id,
                    Recipe.is_master.is_(False),
                    Recipe.test_sequence.is_(None),
                    Recipe.is_archived.is_(False),
                    Recipe.is_current.is_(True),
                )
                .count()
            )
        return (
            Recipe.scoped()
            .filter(
                Recipe.parent_recipe_id == recipe.id,
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
            )
            .count()
        )

    @staticmethod
    def list_recent_recipe_notes(
        *, recipe_id: int, limit: int = 25
    ) -> list[RecipeLineage]:
        note_types = ("NOTE", "EDIT", "EDIT_OVERRIDE")
        return (
            RecipeLineage.scoped()
            .filter(
                RecipeLineage.recipe_id == recipe_id,
                RecipeLineage.notes.isnot(None),
                RecipeLineage.event_type.in_(note_types),
            )
            .order_by(RecipeLineage.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_group_versions(*, recipe_group_id: int | None) -> list[Recipe]:
        if not recipe_group_id:
            return []
        return (
            Recipe.scoped()
            .filter(Recipe.recipe_group_id == recipe_group_id)
            .order_by(
                Recipe.is_master.desc(),
                Recipe.variation_name.asc().nullsfirst(),
                Recipe.version_number.desc(),
                Recipe.test_sequence.asc().nullsfirst(),
            )
            .all()
        )

    @staticmethod
    def find_previous_master_version(
        *,
        recipe_group_id: int | None,
        version_number: int | None,
    ) -> Recipe | None:
        if not recipe_group_id or version_number is None:
            return None
        return (
            Recipe.scoped()
            .filter(
                Recipe.recipe_group_id == recipe_group_id,
                Recipe.is_master.is_(True),
                Recipe.test_sequence.is_(None),
                Recipe.version_number < version_number,
            )
            .order_by(Recipe.version_number.desc())
            .first()
        )

    @staticmethod
    def get_recipe_by_id(*, recipe_id: int) -> Recipe | None:
        return db.session.get(Recipe, recipe_id)

    @staticmethod
    def add_note_entry(*, recipe: Recipe, note_text: str, user_id: int | None) -> None:
        stamped = append_timestamped_note(None, note_text)
        lineage_entry = RecipeLineage(
            recipe_id=recipe.id,
            event_type="NOTE",
            organization_id=recipe.organization_id,
            user_id=user_id,
            notes=stamped,
        )
        db.session.add(lineage_entry)
        db.session.commit()

    @staticmethod
    def convert_variation_to_parent(
        *, recipe_id: int, actor_user_id: int | None
    ) -> tuple[str, Recipe | None, Recipe | None]:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return "not_found", None, None
        if not recipe.parent_recipe_id:
            return "already_parent", recipe, None

        original_parent = recipe.parent
        recipe.parent_recipe_id = None
        if recipe.name.endswith(" Variation"):
            recipe.name = recipe.name.replace(" Variation", "")

        lineage_entry = RecipeLineage(
            recipe_id=recipe.id,
            source_recipe_id=original_parent.id if original_parent else None,
            event_type="PROMOTE_TO_PARENT",
            organization_id=recipe.organization_id,
            user_id=actor_user_id,
        )
        db.session.add(lineage_entry)
        db.session.commit()
        return "converted", recipe, original_parent or recipe

    @staticmethod
    def get_scoped_recipe_or_404(*, recipe_id: int) -> Recipe:
        return Recipe.scoped().filter_by(id=recipe_id).first_or_404()

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
