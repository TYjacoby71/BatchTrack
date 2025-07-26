
# Import models in dependency order to ensure proper table creation
# Base models first (no foreign key dependencies)
from .models import User, Organization
from .permission import Permission
from .developer_permission import DeveloperPermission  
from .developer_role import DeveloperRole
from .subscription_tier import SubscriptionTier
from .role import Role
from .user_role_assignment import UserRoleAssignment
from .user_preferences import UserPreferences

# System reference data
from .unit import Unit
from .category import IngredientCategory

# Business models that depend on User/Organization
from .inventory import InventoryItem
from .product import Product, ProductVariant, ProductSKU
from .recipe import Recipe

# Models that depend on multiple other models (should be last)
from .batch import Batch
from .reservation import Reservation
from .billing_snapshot import BillingSnapshot
from .pricing_snapshot import PricingSnapshot
from .statistics import UserStats, OrganizationStats

# Make sure all models are available for import
__all__ = [
    'User', 'Organization', 'Permission', 'DeveloperPermission', 'DeveloperRole',
    'SubscriptionTier', 'Role', 'UserRoleAssignment', 'UserPreferences',
    'Unit', 'IngredientCategory', 'InventoryItem', 'Product', 'ProductVariant', 
    'ProductSKU', 'Recipe', 'Batch', 'Reservation', 'BillingSnapshot',
    'PricingSnapshot', 'UserStats', 'OrganizationStats'
]
