from sqlalchemy import extract

from app.models.batch import Batch
from app.models.recipe import Recipe
from app.utils.timezone_utils import TimezoneUtils


def generate_batch_label_code(recipe: Recipe) -> str:
    """
    Generate a consistent batch label code.

    Format: {PREFIX}-{YEAR}-{SEQUENCE}
    - PREFIX: recipe.label_prefix uppercased, or generated from recipe name if missing
    - YEAR: current UTC year
    - SEQUENCE: 3-digit, zero-padded count of batches for this recipe in the year
    """
    prefix = recipe.label_prefix
    if not prefix:
        # Generate prefix from recipe name initials if missing
        prefix = generate_recipe_prefix(recipe.name)
    
    prefix = prefix.upper()
    current_year = TimezoneUtils.utc_now().year

    year_batches = Batch.query.filter(
        Batch.recipe_id == recipe.id,
        extract('year', Batch.started_at) == current_year
    ).count()

    return f"{prefix}-{current_year}-{year_batches + 1:03d}"


def generate_recipe_prefix(recipe_name: str) -> str:
    """
    Generate a recipe prefix from the recipe name.
    
    Takes initials of words in the recipe name.
    If initials are not unique, adds letters.
    Handles variations with v1, v2, etc.
    """
    if not recipe_name:
        return 'RCP'
    
    # Get initials from words
    words = recipe_name.replace('_', ' ').replace('-', ' ').split()
    initials = ''.join([word[0].upper() for word in words if word])
    
    if not initials:
        return 'RCP'
    
    # Limit to reasonable length
    if len(initials) > 4:
        initials = initials[:4]
    elif len(initials) < 2:
        # Pad short initials with first few characters
        initials = (recipe_name[:4].upper().replace(' ', ''))[:4]
    
    return initials

