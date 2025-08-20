"""
Recipe Service Package

This package is the canonical, single-source-of-truth for all recipe-related
operations in the application.

All external modules (routes, other services, etc.) MUST import from this
__init__.py file. They are forbidden from importing from the internal
helper modules (those starting with an underscore).
"""

# Import the public functions from our internal helper modules
from ._core import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    duplicate_recipe
)
from ._production_planning import (
    plan_production, calculate_recipe_requirements,
    calculate_production_cost, check_ingredient_availability
)
from ._scaling import scale_recipe
from ._validation import validate_recipe_data

# Make sure all functions are available
__all__ = [
    'create_recipe', 'update_recipe', 'delete_recipe', 'get_recipe_details',
    'duplicate_recipe', 'plan_production', 'calculate_recipe_requirements',
    'calculate_production_cost', 'check_ingredient_availability', 'scale_recipe',
    'validate_recipe_data'
]

# Backwards compatibility shim for tests and legacy code
class RecipeService:
    """Backwards compatibility shim for tests and legacy code"""

    @staticmethod
    def create_recipe(*args, **kwargs):
        return create_recipe(*args, **kwargs)

    @staticmethod
    def update_recipe(*args, **kwargs):
        return update_recipe(*args, **kwargs)

    @staticmethod
    def delete_recipe(*args, **kwargs):
        return delete_recipe(*args, **kwargs)

    @staticmethod
    def plan_production(*args, **kwargs):
        return plan_production(*args, **kwargs)

    @staticmethod
    def scale_recipe(*args, **kwargs):
        return scale_recipe(*args, **kwargs)

    @staticmethod
    def validate_recipe_data(*args, **kwargs):
        return validate_recipe_data(*args, **kwargs)