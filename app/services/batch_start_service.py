"""Batch start boundary service.

Synopsis:
Encapsulates recipe lookup for start-batch flows so route handlers avoid direct
model/session access when resolving the source recipe.
"""

from __future__ import annotations

from app.models.recipe import Recipe
from app.services.recipe_service import get_recipe_details


class BatchStartService:
    """Service helpers for start-batch route dependencies."""

    @staticmethod
    def get_startable_recipe(recipe_id: int) -> Recipe | None:
        return get_recipe_details(recipe_id)
