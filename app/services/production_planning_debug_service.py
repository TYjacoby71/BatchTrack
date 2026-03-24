"""Production planning debug service boundary.

Synopsis:
Encapsulates recipe/container debug data retrieval for production planning routes.
"""

from __future__ import annotations

from app.extensions import db
from app.models import IngredientCategory, InventoryItem, Recipe


class ProductionPlanningDebugService:
    """Service helpers for production-planning debug endpoints."""

    @staticmethod
    def get_recipe(recipe_id: int) -> Recipe | None:
        if not recipe_id:
            return None
        return db.session.get(Recipe, recipe_id)

    @staticmethod
    def get_container_category_for_org(
        *, organization_id: int | None
    ) -> IngredientCategory | None:
        if not organization_id:
            return None
        return (
            IngredientCategory.scoped()
            .filter_by(
                name="Container",
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def list_containers_for_org_category(
        *, organization_id: int | None, category_id: int | None
    ) -> list[InventoryItem]:
        if not organization_id or not category_id:
            return []
        return (
            InventoryItem.scoped()
            .filter_by(
                organization_id=organization_id,
                category_id=category_id,
            )
            .all()
        )

    @staticmethod
    def serialize_allowed_containers(recipe: Recipe) -> list[str]:
        allowed = getattr(recipe, "allowed_containers", None) or []
        return [str(container_id) for container_id in allowed]

    @staticmethod
    def list_org_container_options(
        *, organization_id: int | None, container_category_id: int | None
    ) -> list[dict[str, object]]:
        containers = ProductionPlanningDebugService.list_containers_for_org_category(
            organization_id=organization_id,
            category_id=container_category_id,
        )
        return [
            {
                "id": container.id,
                "name": container.container_display_name,
                "capacity": getattr(container, "capacity", 0),
            }
            for container in containers
        ]
