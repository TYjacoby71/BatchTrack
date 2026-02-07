"""Code generators for recipes and batches.

Synopsis:
Generates batch labels and recipe label prefixes via the lineage service.

Glossary:
- Batch label: Human-readable batch identifier.
- Label prefix: Recipe-level prefix used in batch labels.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.extensions import db
from app.models.batch import BatchSequence
from app.models import User
from app.models.recipe import Recipe
from app.models.db_dialect import is_postgres
from app.services.lineage_service import generate_batch_label, generate_label_prefix
from app.utils.timezone_utils import TimezoneUtils

__all__ = ["generate_batch_label_code", "generate_recipe_prefix"]


# --- Batch label generator ---
# Purpose: Generate a batch label for a recipe.
def generate_batch_label_code(recipe: Recipe) -> str:
    """
    Generate a consistent batch label code.

    Format: {GROUP}{MASTER}-[{VAR}{VER}]-[T{TEST}]-{YEAR}-{SEQUENCE}
    - GROUP: recipe_group.prefix (or fallback prefix)
    - MASTER: master branch version number
    - VAR/VER: variation prefix and version (if applicable)
    - TEST: test sequence (if applicable)
    - SEQUENCE: 3-digit, zero-padded org-wide counter for the year
    """
    current_year = TimezoneUtils.utc_now().year

    org_id = recipe.organization_id
    if not org_id and getattr(recipe, "organization", None):
        org_id = getattr(recipe.organization, "id", None)
    if not org_id and getattr(recipe, "created_by", None):
        creator = db.session.get(User, recipe.created_by)
        org_id = getattr(creator, "organization_id", None) if creator else None
    if not org_id:
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                org_id = current_user.organization_id
        except Exception:
            org_id = None
    if not org_id:
        raise ValueError("Batch label generation requires a valid organization id.")

    sequence = _next_batch_sequence(org_id, current_year)
    return generate_batch_label(recipe, current_year, sequence)


# --- Recipe prefix generator ---
# Purpose: Generate a label prefix from a recipe name.
def generate_recipe_prefix(recipe_name: str, org_id: int | None = None) -> str:
    """
    Generate a recipe prefix from the recipe name.
    """
    return generate_label_prefix(recipe_name, org_id)


# --- Batch sequence allocator ---
# Purpose: Fetch the next batch sequence for org/year.
def _next_batch_sequence(org_id: int, year: int) -> int:
    if is_postgres():
        now = TimezoneUtils.utc_now()
        table = BatchSequence.__table__
        stmt = (
            pg_insert(table)
            .values(
                organization_id=org_id,
                year=year,
                current_sequence=1,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["organization_id", "year"],
                set_={
                    "current_sequence": table.c.current_sequence + 1,
                    "updated_at": now,
                },
            )
            .returning(table.c.current_sequence)
        )
        return int(db.session.execute(stmt).scalar_one())

    counter = BatchSequence.query.filter_by(
        organization_id=org_id,
        year=year,
    ).first()
    if not counter:
        counter = BatchSequence(
            organization_id=org_id,
            year=year,
            current_sequence=1,
            created_at=TimezoneUtils.utc_now(),
            updated_at=TimezoneUtils.utc_now(),
        )
        db.session.add(counter)
        db.session.flush()
        return 1

    counter.current_sequence = int(counter.current_sequence or 0) + 1
    counter.updated_at = TimezoneUtils.utc_now()
    db.session.flush()
    return int(counter.current_sequence)
