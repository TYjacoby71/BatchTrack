# Database Models & Relationships

## Synopsis
This document maps the current BatchTrack model layer and highlights how tenant scoping, inventory, production, permissions, and billing-related tables connect. Use this as the system-level orientation guide before changing schema, migrations, or service logic that depends on model relationships.

## Glossary
- **Scoped model**: A model carrying `organization_id` and tenant-bound query semantics.
- **Global catalog model**: Platform-owned model shared across tenants (for example `GlobalItem`).
- **Lifecycle model**: Model that records process states/events (for example batch, reservation, or domain events).

## Canonical Source of Truth
- Primary package: `app/models/`
- Registry/export hub: `app/models/__init__.py`
- Active compatibility export layer: `app/models/models.py`

## Domain Model Map (Current)

### 1. Tenant Identity and User State
- `Organization` (`app/models/models.py`)
- `User` (`app/models/models.py`)
- `UserPreferences` (`app/models/user_preferences.py`)
- `PendingSignup` (`app/models/pending_signup.py`)

### 2. Permissions and Role Assignment
- `Permission` (`app/models/permission.py`)
- `Role` (`app/models/role.py`)
- `UserRoleAssignment` (`app/models/user_role_assignment.py`)
- `DeveloperRole` (`app/models/developer_role.py`)
- `DeveloperPermission` (`app/models/developer_permission.py`)

### 3. Recipes and Production Execution
- `RecipeGroup`, `Recipe`, `RecipeIngredient`, `RecipeConsumable`, `RecipeLineage` (`app/models/recipe.py`)
- `Batch`, `BatchSequence`, `BatchIngredient`, `BatchContainer`, `BatchConsumable`, `BatchTimer` (`app/models/batch.py`)
- Extra batch adjustment rows (`ExtraBatchIngredient`, `ExtraBatchContainer`, `ExtraBatchConsumable`) (`app/models/batch.py`)

### 4. Inventory and Global Library
- `InventoryItem`, `InventoryHistory`, `BatchInventoryLog` (`app/models/inventory.py`)
- `InventoryLot` (`app/models/inventory_lot.py`)
- `UnifiedInventoryHistory` (`app/models/unified_inventory_history.py`)
- `GlobalItem`, `GlobalItemAlias` (`app/models/global_item.py`, `app/models/global_item_alias.py`)
- Ingredient reference taxonomy models (`IngredientDefinition`, `PhysicalForm`, `Variation`, tag bridge tables) (`app/models/ingredient_reference.py`)
- Categories/taxonomy: `IngredientCategory`, `InventoryCategory`, `Tag` (`app/models/category.py`)

### 5. Products and Commerce
- `Product`, `ProductVariant`, `ProductSKU` (`app/models/product.py`)
- `ProductCategory` (`app/models/product_category.py`)

### 6. Billing, Access, and Retention State
- `SubscriptionTier` (`app/models/subscription_tier.py`)
- `Addon`, `OrganizationAddon` (`app/models/addon.py`)
- `StripeEvent` (`app/models/stripe_event.py`)
- `RetentionDeletionQueue`, `StorageAddonPurchase`, `StorageAddonSubscription` (`app/models/retention.py`)
- `Reservation` (`app/models/reservation.py`)

### 7. Telemetry, Statistics, and Operations
- `UserStats`, `OrganizationStats`, `OrganizationLeaderboardStats`, and related stats models (`app/models/statistics.py`)
- `DomainEvent` (`app/models/domain_event.py`)
- `PricingSnapshot` (`app/models/pricing_snapshot.py`)
- `FeatureFlag` (`app/models/feature_flag.py`)
- `AppSetting` (`app/models/app_setting.py`)
- `BatchBotUsage`, `BatchBotCreditBundle`, `FreshnessSnapshot` (`app/models/batchbot_usage.py`, `app/models/batchbot_credit.py`, `app/models/freshness_snapshot.py`)

## Relationship Highlights

### Tenant Boundary
```
Organization
├── User
├── Role (org-scoped variants)
├── InventoryItem
├── Recipe / Batch
└── Product / SKU
```

### Access Control
```
User
└── UserRoleAssignment ──> Role ──> Permission
```

### Recipe to Batch to Inventory
```
RecipeGroup
└── Recipe (lineage/versioned)
    └── Batch
        ├── BatchIngredient / BatchContainer / BatchConsumable
        └── Inventory movement logs
```

### Global Catalog Linkage
```
GlobalItem (platform-owned)
└── InventoryItem.global_item_id (nullable, ON DELETE SET NULL)
```

## Scoping and Timestamp Standards
- Prefer `ScopedModelMixin` models for tenant data.
- Scope queries by `organization_id` in services/routes unless explicitly in developer/global context.
- Use timezone-aware UTC defaults (`TimezoneUtils.utc_now`) for model timestamps.
- Keep archival/deactivation semantics explicit (`is_active`, `is_archived`) where lifecycle state matters.

## Compatibility Surface (Current Behavior)
- `app/models/models.py` remains part of the supported import surface for app and test call sites.
- `Ingredient` remains an active compatibility alias to `InventoryItem`; new development should prefer importing `InventoryItem` directly.

## Relevance Check (2026-02-17)
This document was refreshed against active model modules in `app/models/` and current export wiring in `app/models/__init__.py`.
