"""Recipe library view service boundary.

Synopsis:
Encapsulates read/query paths used by public recipe-library routes so
`recipe_library/routes.py` stays transport-focused.
"""

from __future__ import annotations

from sqlalchemy import func, nullslast, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Organization, ProductCategory, Recipe
from app.models.statistics import BatchStats


class RecipeLibraryViewService:
    """Data-access helpers for public recipe-library routes."""

    @staticmethod
    def _base_public_recipe_query():
        return (
            Recipe.query.options(
                joinedload(Recipe.product_category),
                joinedload(Recipe.stats),
                joinedload(Recipe.organization),
            )
            .outerjoin(Organization, Recipe.organization_id == Organization.id)
            .filter(
                Recipe.is_public.is_(True),
                Recipe.status == "published",
                Recipe.marketplace_status == "listed",
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
                (Organization.recipe_library_blocked.is_(False))
                | (Organization.recipe_library_blocked.is_(None)),
            )
        )

    @staticmethod
    def _apply_tokenized_recipe_search(query, search_query: str):
        if not search_query:
            return query
        tokens = [token.strip() for token in search_query.split() if token.strip()]
        for token in tokens:
            like_expr = f"%{token}%"
            query = query.filter(
                or_(
                    Recipe.name.ilike(like_expr),
                    Recipe.public_description.ilike(like_expr),
                )
            )
        return query

    @staticmethod
    def _apply_recipe_sort(query, sort_mode: str):
        if sort_mode == "oldest":
            return query.order_by(Recipe.updated_at.asc())
        if sort_mode == "downloads":
            return query.order_by(
                Recipe.download_count.desc(), Recipe.updated_at.desc(), Recipe.name.asc()
            )
        if sort_mode == "price_high":
            return query.order_by(
                nullslast(Recipe.sale_price.desc()), Recipe.updated_at.desc()
            )
        return query.order_by(Recipe.updated_at.desc(), Recipe.name.asc())

    @staticmethod
    def list_public_library_recipes(
        *,
        search_query: str,
        category_filter: int | None,
        sale_filter: str,
        org_filter: int | None,
        origin_filter: str,
        sort_mode: str,
        limit: int = 30,
    ) -> list[Recipe]:
        query = RecipeLibraryViewService._base_public_recipe_query()
        if category_filter:
            query = query.filter(Recipe.category_id == category_filter)
        if sale_filter == "sale":
            query = query.filter(Recipe.is_for_sale.is_(True))
        elif sale_filter == "free":
            query = query.filter(Recipe.is_for_sale.is_(False))
        if org_filter:
            query = query.filter(Recipe.organization_id == org_filter)
        if origin_filter == "batchtrack":
            query = query.filter(Recipe.org_origin_type == "batchtrack_native")
        elif origin_filter == "purchased":
            query = query.filter(Recipe.org_origin_purchased.is_(True))
        elif origin_filter == "authored":
            query = query.filter(
                (Recipe.org_origin_type.in_(["authored", "published"]))
                | (Recipe.org_origin_type.is_(None))
            )
        query = RecipeLibraryViewService._apply_tokenized_recipe_search(
            query, search_query
        )
        query = RecipeLibraryViewService._apply_recipe_sort(query, sort_mode)
        return query.limit(limit).all()

    @staticmethod
    def list_public_categories() -> list[ProductCategory]:
        return ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    @staticmethod
    def list_public_origin_organizations() -> list[dict[str, object]]:
        organizations = (
            db.session.query(Organization.id, Organization.name)
            .join(Recipe, Recipe.organization_id == Organization.id)
            .filter(
                Recipe.is_public.is_(True),
                Recipe.status == "published",
                Recipe.marketplace_status == "listed",
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
                (Organization.recipe_library_blocked.is_(False))
                | (Organization.recipe_library_blocked.is_(None)),
            )
            .distinct()
            .order_by(Organization.name.asc())
            .all()
        )
        return [{"id": org.id, "name": org.name} for org in organizations]

    @staticmethod
    def get_public_recipe_or_404(recipe_id: int) -> Recipe:
        return (
            Recipe.query.options(
                joinedload(Recipe.product_category),
                joinedload(Recipe.stats),
            )
            .outerjoin(Organization, Recipe.organization_id == Organization.id)
            .filter(
                Recipe.id == recipe_id,
                Recipe.is_public.is_(True),
                Recipe.status == "published",
                Recipe.marketplace_status == "listed",
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
                (Organization.recipe_library_blocked.is_(False))
                | (Organization.recipe_library_blocked.is_(None)),
            )
            .first_or_404()
        )

    @staticmethod
    def get_organization_or_404(organization_id: int) -> Organization:
        return db.get_or_404(Organization, organization_id)

    @staticmethod
    def list_org_marketplace_recipes(
        *,
        organization_id: int,
        search_query: str,
        sale_filter: str,
        sort_mode: str,
    ) -> list[Recipe]:
        query = Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.stats),
        ).filter(
            Recipe.organization_id == organization_id,
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
        )
        if sale_filter == "sale":
            query = query.filter(Recipe.is_for_sale.is_(True))
        elif sale_filter == "free":
            query = query.filter(Recipe.is_for_sale.is_(False))
        query = RecipeLibraryViewService._apply_tokenized_recipe_search(
            query, search_query
        )
        query = RecipeLibraryViewService._apply_recipe_sort(query, sort_mode)
        return query.all()

    @staticmethod
    def fetch_cost_rollups(recipe_ids: list[int]) -> dict[int, dict[str, float]]:
        if not recipe_ids:
            return {}
        rows = (
            db.session.query(
                BatchStats.recipe_id,
                func.avg(BatchStats.actual_ingredient_cost).label("ingredient_cost"),
                func.avg(BatchStats.total_actual_cost).label("total_cost"),
            )
            .filter(BatchStats.recipe_id.in_(recipe_ids))
            .group_by(BatchStats.recipe_id)
            .all()
        )
        return {
            row.recipe_id: {
                "ingredient_cost": float(row.ingredient_cost or 0),
                "total_cost": float(row.total_cost or 0),
            }
            for row in rows
        }
