from __future__ import annotations

from sqlalchemy import extract

from app.models.batch import Batch
from app.models.recipe import Recipe
from app.utils.timezone_utils import TimezoneUtils

__all__ = ["generate_batch_label_code", "generate_recipe_prefix"]


def generate_batch_label_code(
    recipe: Recipe,
    organization_id: int | None = None,
    *,
    sequence_offset: int = 0,
    suffix: str | None = None,
) -> str:
    """
    Generate a consistent batch label code.

    Format: {PREFIX}-{YEAR}-{SEQUENCE}
    - PREFIX: recipe.label_prefix uppercased, or generated from recipe name if missing
    - YEAR: current UTC year
    - SEQUENCE: 3-digit, zero-padded count of batches for this recipe in the year
    """
    prefix = (recipe.label_prefix or generate_recipe_prefix(recipe.name)).upper()
    current_year = TimezoneUtils.utc_now().year

    query = Batch.query.filter(extract("year", Batch.started_at) == current_year)
    if organization_id is not None:
        query = query.filter(Batch.organization_id == organization_id)
    query = query.filter(Batch.label_code.like(f"{prefix}-{current_year}-%"))

    year_batches = query.count() or 0
    sequence = max(1, year_batches + 1 + max(sequence_offset, 0))
    base_label = f"{prefix}-{current_year}-{sequence:03d}"
    if suffix:
        return f"{base_label}-{suffix}".upper()
    return base_label


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
