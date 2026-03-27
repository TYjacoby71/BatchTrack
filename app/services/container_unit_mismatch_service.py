"""Container unit-mismatch drawer service boundary.

Synopsis:
Encapsulates recipe/container lookup and yield update persistence for container
unit-mismatch drawer routes so handlers stay transport-only.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

import logging

from app.extensions import db
from app.models import InventoryItem, Recipe

logger = logging.getLogger(__name__)


class ContainerUnitMismatchService:
    """Service helpers for container unit-mismatch drawer flows."""

    @staticmethod
    def get_recipe_for_org(
        *, recipe_id: int, organization_id: int | None
    ) -> Recipe | None:
        if not recipe_id or not organization_id:
            return None
        return (
            Recipe.scoped()
            .filter_by(
                id=recipe_id,
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def list_allowed_containers_for_org(
        *, allowed_ids: list[int], organization_id: int | None
    ) -> list[InventoryItem]:
        if not allowed_ids or not organization_id:
            return []
        return (
            InventoryItem.scoped()
            .filter(
                InventoryItem.id.in_(allowed_ids),
                InventoryItem.organization_id == organization_id,
            )
            .all()
        )

    @staticmethod
    def update_recipe_yield(
        *,
        recipe: Recipe,
        predicted_yield: float,
        predicted_yield_unit: str,
    ) -> None:
        recipe.predicted_yield = predicted_yield
        recipe.predicted_yield_unit = predicted_yield_unit
        try:
            db.session.commit()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/container_unit_mismatch_service.py:58",
                exc_info=True,
            )
            db.session.rollback()
            raise
