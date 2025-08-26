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
# Production planning moved to dedicated service package
from ..production_planning import plan_production_comprehensive as plan_production
from ._scaling import scale_recipe
from ._validation import validate_recipe_data
from ..stock_check.core import UniversalStockCheckService

def check_recipe_stock(recipe, scale: float = 1.0):
    """Check stock for recipe using USCS directly"""
    uscs = UniversalStockCheckService()
    return uscs.check_recipe_stock(recipe.id, scale)

# Make sure all functions are available
__all__ = [
    'create_recipe', 'update_recipe', 'delete_recipe', 'get_recipe_details',
    'duplicate_recipe', 'plan_production', 'scale_recipe',
    'validate_recipe_data', 'check_recipe_stock'
]

# Backwards compatibility shim for tests and legacy code
class RecipeService:
    """Backwards compatibility shim for tests and legacy code"""

    @staticmethod
    def create_recipe(name, ingredients, yield_amount, unit, notes=None, category=None, tags=None, batch_size=None, organization_id=None, created_by=None):
        return create_recipe(name, ingredients, yield_amount, unit, notes, category, tags, batch_size, organization_id, created_by)

    @staticmethod
    def update_recipe(recipe_id, name=None, ingredients=None, yield_amount=None, unit=None, notes=None, category=None, tags=None, batch_size=None):
        return update_recipe(recipe_id, name, ingredients, yield_amount, unit, notes, category, tags, batch_size)

    @staticmethod
    def delete_recipe(recipe_id):
        return delete_recipe(recipe_id)

    @staticmethod
    def plan_production(recipe_id, scale=1.0, container_id=None, check_containers=False):
        return plan_production(recipe_id, scale, container_id, check_containers)

    @staticmethod
    def scale_recipe(recipe_id, scale_factor):
        return scale_recipe(recipe_id, scale_factor)

    @staticmethod
    def validate_recipe_data(name, ingredients=None, yield_amount=None, recipe_id=None, notes=None, category=None, tags=None, batch_size=None):
        return validate_recipe_data(name, ingredients, yield_amount, recipe_id, notes, category, tags, batch_size)

    @staticmethod
    def check_recipe_stock(recipe_id, scale=1.0):
        from ..stock_check.core import UniversalStockCheckService
        uscs = UniversalStockCheckService()
        return uscs.check_recipe_stock(recipe_id, scale)