"""Lineage-aware batch counting utilities.

Synopsis:
Provides helpers to count batches for an exact recipe lineage/version.

Glossary:
- Lineage ID: Stable identifier for a specific master/variation/test branch version.
- Target version: Recipe version id snapshot recorded when a batch starts.
"""

from __future__ import annotations

import sqlalchemy as sa

from app.extensions import db
from app.models import Batch, Recipe
from app.services.lineage_service import generate_lineage_id


def count_batches_for_recipe_lineage(
    recipe: Recipe, *, organization_id: int | None = None
) -> int:
    """Count batches for one specific recipe version/test lineage.

    The query prefers explicit lineage/target-version links and includes a
    conservative legacy fallback for rows that only stored `recipe_id`.
    """
    if not recipe or not getattr(recipe, "id", None):
        return 0

    lineage_id = generate_lineage_id(recipe)
    recipe_id = int(recipe.id)
    effective_org_id = (
        organization_id
        if organization_id is not None
        else getattr(recipe, "organization_id", None)
    )

    predicates: list = [
        Batch.target_version_id == recipe_id,
        sa.and_(Batch.target_version_id.is_(None), Batch.recipe_id == recipe_id),
    ]
    if lineage_id:
        predicates.append(Batch.lineage_id == lineage_id)

    query = db.session.query(sa.func.count(sa.distinct(Batch.id))).filter(
        sa.or_(*predicates)
    )
    if effective_org_id is not None:
        query = query.filter(Batch.organization_id == effective_org_id)

    return int(query.scalar() or 0)


__all__ = ["count_batches_for_recipe_lineage"]
