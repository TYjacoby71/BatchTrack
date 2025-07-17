
"""Models package - imports all models for the application"""
from ..extensions import db
from .mixins import ScopedModelMixin
from .models import (
    Organization, User, Unit, CustomUnitMapping, IngredientCategory, 
    ConversionLog, RecipeIngredient, Recipe, Batch, BatchIngredient, 
    BatchContainer, ExtraBatchContainer, InventoryHistory, BatchTimer, 
    ExtraBatchIngredient, InventoryItem, BatchInventoryLog, Tag
)
from .product import Product, ProductVariant, ProductSKU, ProductSKUHistory
from .reservation import Reservation
from .role import Role
from .permission import Permission, role_permission
from .user_role_assignment import UserRoleAssignment
from .user_preferences import *

# Re-export everything for convenience
__all__ = [
    'db', 'ScopedModelMixin', 'Organization', 'User', 'Unit', 'CustomUnitMapping', 'IngredientCategory', 
    'ConversionLog', 'RecipeIngredient', 'Recipe', 'Batch', 'BatchIngredient', 
    'BatchContainer', 'ExtraBatchContainer', 'InventoryHistory', 'BatchTimer', 
    'ExtraBatchIngredient', 'InventoryItem', 'BatchInventoryLog', 'Tag',
    'Product', 'ProductVariant', 'ProductSKU', 'ProductSKUHistory', 'Reservation', 
    'Role', 'Permission', 'role_permission', 'UserRoleAssignment',
    '*'
]
