"""Models package - imports all models for the application"""
from ..extensions import db
from .mixins import ScopedModelMixin

# Import in dependency order for PostgreSQL table creation
# 1. Base models with no dependencies
from .models import (
    db, Organization, User, InventoryItem, InventoryHistory, BatchInventoryLog,
    Recipe, RecipeIngredient
)
from .batch import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, BatchTimer, ExtraBatchIngredient
from .unit import Unit, CustomUnitMapping, ConversionLog
from .category import IngredientCategory, Tag
from .statistics import RecipeUsageLog, ConversionStatistic
from .stripe_event import StripeEvent
from .pricing_snapshot import PricingSnapshot
from .billing_snapshot import BillingSnapshot
from .user_preferences import UserPreferences
from .user_role_assignment import UserRoleAssignment
from .developer_permission import DeveloperPermission
from .developer_role import DeveloperRole
from .product import Product, ProductSKU
from .subscription_tier import SubscriptionTier
from .permission import Permission
from .role import Role

__all__ = [
    "db", "Organization", "User", "InventoryItem", "InventoryHistory", "BatchInventoryLog",
    "Recipe", "RecipeIngredient", "Batch", "BatchIngredient", "BatchContainer", 
    "ExtraBatchContainer", "BatchTimer", "ExtraBatchIngredient", "Unit", 
    "CustomUnitMapping", "ConversionLog", "IngredientCategory", "Tag",
    "RecipeUsageLog", "ConversionStatistic", "StripeEvent", "PricingSnapshot",
    "BillingSnapshot", "UserPreferences", "UserRoleAssignment", 
    "DeveloperPermission", "DeveloperRole", "Product", "ProductSKU",
    "SubscriptionTier", "Permission", "Role"
]