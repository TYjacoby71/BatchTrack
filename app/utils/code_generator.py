from sqlalchemy import extract

from app.models.batch import Batch
from app.models.recipe import Recipe
from app.utils.timezone_utils import TimezoneUtils


def generate_batch_label_code(recipe: Recipe) -> str:
    """
    Generate a consistent batch label code.

    Format: {PREFIX}-{YEAR}-{SEQUENCE}
    - PREFIX: recipe.label_prefix uppercased, or 'BTH' if missing
    - YEAR: current UTC year
    - SEQUENCE: 3-digit, zero-padded count of batches for this recipe in the year
    """
    prefix = (recipe.label_prefix or 'BTH').upper()
    current_year = TimezoneUtils.utc_now().year

    year_batches = Batch.query.filter(
        Batch.recipe_id == recipe.id,
        extract('year', Batch.started_at) == current_year
    ).count()

    return f"{prefix}-{current_year}-{year_batches + 1:03d}"

