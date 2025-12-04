"""Lineage logging helpers."""

from __future__ import annotations

import logging
from typing import Optional

from flask_login import current_user

from ...extensions import db
from ...models.recipe import RecipeLineage

logger = logging.getLogger(__name__)


def _log_lineage_event(
    recipe,
    event_type: str,
    source_recipe_id: Optional[int] | None = None,
    notes: Optional[str] | None = None,
) -> None:
    """Persist a lineage audit row but never block recipe creation."""
    try:
        lineage = RecipeLineage(
            recipe_id=recipe.id,
            source_recipe_id=source_recipe_id,
            event_type=event_type,
            organization_id=recipe.organization_id,
            user_id=getattr(current_user, 'id', None),
            notes=notes
        )
        db.session.add(lineage)
    except Exception as exc:  # pragma: no cover - audit best-effort
        logger.debug(f"Unable to write recipe lineage event ({event_type}): {exc}")


__all__ = [
    "_log_lineage_event",
]
