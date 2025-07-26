
"""Models package - imports all models for the application"""
from ..extensions import db
from .mixins import ScopedModelMixin

# Import in dependency order for PostgreSQL table creation
# 1. Base models with no dependencies
from .models import Organization, User
from .subscription_tier import SubscriptionTier
from .unit import Unit
from .category import IngredientCategory, Tag

# 2. Permission system models
from .permission import Permission, role_permission
from .developer_permission import DeveloperPermission
from .developer_role import DeveloperRole
from .role import Role
from .user_role_assignment import UserRoleAssignment

# 3. User-related models that depend on User
from .user_preferences import UserPreferences
from .statistics import UserStats, OrganizationStats

# 4. Business models that depend on basic models
from .inventory import InventoryItem, InventoryHistory, BatchInventoryLog
from .recipe import Recipe, RecipeIngredient
from .product import Product, ProductVariant, ProductSKU, ProductSKUHistory

# 5. Complex models with multiple dependencies (load last)
from .batch import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, BatchTimer, ExtraBatchIngredient
from .reservation import Reservation
from .unit import CustomUnitMapping, ConversionLog
from .billing_snapshot import BillingSnapshot
from .pricing_snapshot import PricingSnapshot

# Re-export everything for convenience
__all__ = [
    'db', 'ScopedModelMixin', 'Organization', 'User',
    'InventoryItem', 'InventoryHistory', 'BatchInventoryLog',
    'Recipe', 'RecipeIngredient',
    'Batch', 'BatchIngredient', 'BatchContainer', 'ExtraBatchContainer', 'BatchTimer', 'ExtraBatchIngredient',
    'Unit', 'CustomUnitMapping', 'ConversionLog',
    'IngredientCategory', 'Tag',
    'Product', 'ProductVariant', 'ProductSKU', 'ProductSKUHistory', 'Reservation', 
    'Role', 'Permission', 'role_permission', 'UserRoleAssignment', 'UserPreferences', 'UserStats', 
    'OrganizationStats', 'SubscriptionTier', 'DeveloperPermission', 'DeveloperRole',
    'BillingSnapshot', 'PricingSnapshot'
]
