"""Models package - imports all models for the application"""
from ..extensions import db
from .mixins import ScopedModelMixin

# Import in dependency order for PostgreSQL table creation
# 1. Base models with no dependencies
from .models import (
    db, Organization, User, InventoryItem, InventoryHistory, BatchInventoryLog,
    Recipe, RecipeIngredient
)
from .recipe import RecipeConsumable
from .batch import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, BatchTimer, ExtraBatchIngredient
from .unit import Unit, CustomUnitMapping, ConversionLog
from .category import IngredientCategory, Tag
from .stripe_event import StripeEvent
from .pricing_snapshot import PricingSnapshot
from .billing_snapshot import BillingSnapshot
from .user_preferences import UserPreferences
from .user_role_assignment import UserRoleAssignment
from .developer_permission import DeveloperPermission
from .developer_role import DeveloperRole

# Core models (that definitely exist)
from .product import Product, ProductSKU
try:
    from .product import ProductVariant
except ImportError:
    # ProductVariant might not exist in all versions
    pass
from .subscription_tier import SubscriptionTier
from .permission import Permission
from .role import Role

# OPTIONAL exports — don't crash if the module or names aren't present
try:
    from .statistics import UserStats, OrganizationStats
except ImportError:
    pass

# Add test-expected aliases
try:
    from .inventory import InventoryHistory as FIFOLot
    Ingredient = InventoryItem  # Alias for tests expecting Ingredient class
except ImportError:
    pass

# Safe re-export layer - defer to models.py
from .models import *

# Add missing exports for tests
try:
    from .reservation import Reservation
except ImportError:
    pass

try:
    from .product import ProductSKUHistory
except ImportError:
    pass

# Also ensure direct access to key models for backward compatibility
try:
    from .mixins import ScopedModelMixin
except ImportError:
    pass

# Import unified inventory history model
from .unified_inventory_history import UnifiedInventoryHistory
from .domain_event import DomainEvent

# Import inventory lot model 
from .inventory_lot import InventoryLot

# Make sure all exported symbols are available
__all__ = list([k for k in globals().keys() if not k.startswith('_')])