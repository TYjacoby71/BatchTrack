from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.extensions import db
from app.models.batch import BatchLabelCounter
from app.models import User
from app.models.recipe import Recipe
from app.models.db_dialect import is_postgres
from app.utils.timezone_utils import TimezoneUtils

__all__ = ["generate_batch_label_code", "generate_recipe_prefix"]


def generate_batch_label_code(recipe: Recipe) -> str:
    """
    Generate a consistent batch label code.

    Format: {PREFIX}-{YEAR}-{SEQUENCE}
    - PREFIX: recipe.label_prefix uppercased, or generated from recipe name if missing
    - YEAR: current UTC year
    - SEQUENCE: 3-digit, zero-padded count of batches for this recipe in the year
    """
    prefix = (recipe.label_prefix or generate_recipe_prefix(recipe.name)).upper()
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

    sequence = _next_batch_sequence(org_id, prefix, current_year)
    return f"{prefix}-{current_year}-{sequence:03d}"


def generate_recipe_prefix(recipe_name: str) -> str:
    """
    Generate a recipe prefix from the recipe name.
    """
    if not recipe_name:
        return "RCP"

    words = recipe_name.replace("_", " ").replace("-", " ").split()
    initials = "".join(word[0].upper() for word in words if word)

    if not initials:
        return "RCP"

    if len(initials) > 4:
        initials = initials[:4]
    elif len(initials) < 2:
        initials = (recipe_name.upper().replace(" ", ""))[:4] or "RCP"

    return initials


def _next_batch_sequence(org_id: int, prefix: str, year: int) -> int:
    if is_postgres():
        now = TimezoneUtils.utc_now()
        table = BatchLabelCounter.__table__
        stmt = (
            pg_insert(table)
            .values(
                organization_id=org_id,
                prefix=prefix,
                year=year,
                next_sequence=1,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["organization_id", "prefix", "year"],
                set_={
                    "next_sequence": table.c.next_sequence + 1,
                    "updated_at": now,
                },
            )
            .returning(table.c.next_sequence)
        )
        return int(db.session.execute(stmt).scalar_one())

    counter = BatchLabelCounter.query.filter_by(
        organization_id=org_id,
        prefix=prefix,
        year=year,
    ).first()
    if not counter:
        counter = BatchLabelCounter(
            organization_id=org_id,
            prefix=prefix,
            year=year,
            next_sequence=1,
            created_at=TimezoneUtils.utc_now(),
            updated_at=TimezoneUtils.utc_now(),
        )
        db.session.add(counter)
        db.session.flush()
        return 1

    counter.next_sequence = int(counter.next_sequence or 0) + 1
    counter.updated_at = TimezoneUtils.utc_now()
    db.session.flush()
    return int(counter.next_sequence)
