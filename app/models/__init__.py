"""Models package - imports all models for the application.

Synopsis:
Central import hub to register models and keep ORM metadata consistent.

Glossary:
- Model registry: List of ORM classes loaded for the app.
- Scoped model: ORM class bound to an organization_id.
"""

from ..extensions import db
from .app_setting import AppSetting
from .batch import (
    Batch,
    BatchConsumable,
    BatchContainer,
    BatchIngredient,
    BatchSequence,
    BatchTimer,
    ExtraBatchConsumable,
    ExtraBatchContainer,
    ExtraBatchIngredient,
)
from .category import IngredientCategory, Tag
from .developer_permission import DeveloperPermission
from .developer_role import DeveloperRole
from .feature_flag import FeatureFlag
from .ingredient_reference import (
    ApplicationTag,
    FunctionTag,
    GlobalItemApplicationTag,
    GlobalItemCategoryTag,
    GlobalItemFunctionTag,
    IngredientCategoryTag,
    IngredientDefinition,
    PhysicalForm,
    Variation,
)
from .mixins import ScopedModelMixin

# Import in dependency order for PostgreSQL table creation
# 1. Base models with no dependencies
from .models import (
    BatchInventoryLog,
    InventoryHistory,
    InventoryItem,
    Organization,
    User,
    db,
)
from .pricing_snapshot import PricingSnapshot

# Core models (that definitely exist)
from .product import Product, ProductSKU
from .product_category import ProductCategory
from .recipe import (
    Recipe,
    RecipeConsumable,
    RecipeGroup,
    RecipeIngredient,
    RecipeLineage,
)
from .recipe_marketplace import RecipeModerationEvent
from .stripe_event import StripeEvent
from .unit import ConversionLog, CustomUnitMapping, Unit
from .user_preferences import UserPreferences
from .user_role_assignment import UserRoleAssignment

try:
    from .product import ProductVariant
except ImportError:
    # ProductVariant might not exist in all versions
    pass
from .pending_signup import PendingSignup
from .permission import Permission
from .role import Role
from .subscription_tier import SubscriptionTier

# OPTIONAL exports — don't crash if the module or names aren't present
try:
    from .statistics import OrganizationStats, UserStats
except ImportError:
    pass

# Add test-expected aliases
try:
    from .unified_inventory_history import UnifiedInventoryHistory as FIFOLot

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

# Also ensure direct access to key models for backward compatibility
try:
    from .mixins import ScopedModelMixin
except ImportError:
    pass

from .batchbot_credit import BatchBotCreditBundle
from .domain_event import DomainEvent
from .freshness_snapshot import FreshnessSnapshot

# Import inventory lot model
from .inventory_lot import InventoryLot

# Import unified inventory history model
from .unified_inventory_history import UnifiedInventoryHistory

# Make sure all exported symbols are available
__all__ = list([k for k in globals().keys() if not k.startswith("_")])
