
"""Models package - imports all models for the application"""
from ..extensions import db
from .mixins import ScopedModelMixin
from .models import Organization, User
from .inventory import InventoryItem, InventoryHistory, BatchInventoryLog
from .recipe import Recipe, RecipeIngredient
from .batch import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, BatchTimer, ExtraBatchIngredient
from .unit import Unit, CustomUnitMapping, ConversionLog
from .category import IngredientCategory, Tag
from .product import Product, ProductVariant, ProductSKU, ProductSKUHistory
from .reservation import Reservation
from .role import Role
from .permission import Permission, role_permission
from .user_role_assignment import UserRoleAssignment
from .user_preferences import *
from .statistics import UserStats, OrganizationStats, Leaderboard
from .subscription import Subscription
from .subscription_tier import SubscriptionTier
from .developer_permission import DeveloperPermission
from .developer_role import DeveloperRole

# Re-export everything for convenience
__all__ = [
    'db', 'ScopedModelMixin', 'Organization', 'User',
    'InventoryItem', 'InventoryHistory', 'BatchInventoryLog',
    'Recipe', 'RecipeIngredient',
    'Batch', 'BatchIngredient', 'BatchContainer', 'ExtraBatchContainer', 'BatchTimer', 'ExtraBatchIngredient',
    'Unit', 'CustomUnitMapping', 'ConversionLog',
    'IngredientCategory', 'Tag',
    'Product', 'ProductVariant', 'ProductSKU', 'ProductSKUHistory', 'Reservation', 
    'Role', 'Permission', 'role_permission', 'UserRoleAssignment', 'UserStats', 
    'OrganizationStats', 'Leaderboard', 'Subscription', 'DeveloperPermission', 'DeveloperRole',
    '*'
]
