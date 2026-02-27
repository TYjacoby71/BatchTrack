"""Batch counting utilities.

Synopsis:
Provides helpers to count batches for an exact recipe row.

Glossary:
- Recipe row: Master/variation/test version represented by one recipe.id.
"""

from __future__ import annotations

from app.models import Batch, Recipe


def count_batches_for_recipe(
    recipe: Recipe, *, organization_id: int | None = None
) -> int:
    """Count batches for one specific recipe row."""
    if not recipe or not getattr(recipe, "id", None):
        return 0

    recipe_id = int(recipe.id)
    effective_org_id = (
        organization_id
        if organization_id is not None
        else getattr(recipe, "organization_id", None)
    )

    query = Batch.query.filter(Batch.recipe_id == recipe_id)
    if effective_org_id is not None:
        query = query.filter(Batch.organization_id == effective_org_id)

    return int(query.count() or 0)


__all__ = ["count_batches_for_recipe"]
