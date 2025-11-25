# BatchTrack Services Documentation

## Service Overview

BatchTrack uses a service-oriented architecture where each service has complete authority over its domain. **Never bypass these services** - always use the proper service for any operation in its domain.

For in-context user-fixable errors, services should return a `drawer_payload` (see `docs/WALL_OF_DRAWERS_PROTOCOL.md`).

## Core Services

### 1. FIFO Service (`app/blueprints/fifo/services.py`)

**Authority:** All inventory deduction order and batch lot management

**Key Endpoints / Modules:**
- API: `app/blueprints/api/fifo_routes.py` (details, summaries)
- Ops: `app/services/inventory_adjustment/_fifo_ops.py` (deductions)

**Usage Examples:**
```python
# Deduct via Inventory Adjustment service (authoritative path)
from app.services.inventory_adjustment import process_inventory_adjustment

process_inventory_adjustment({
    "inventory_item_id": ingredient.inventory_item_id,
    "change_type": "deduct",
    "quantity": required_amount,
    "unit": ingredient.unit,
    "reason": "batch",
    "batch_id": batch.id
})
```

**Rules:**
- Always deducts from oldest batches first
- Tracks exact batch lot consumption
- Maintains inventory history with batch references
- Handles partial deductions across multiple lots

### 2. Inventory Adjustment Service (`app/services/inventory_adjustment.py`)

**Authority:** All inventory changes and history logging

**Key Functions:**
- `adjust_inventory(inventory_id, amount, unit_id, reason, cost_per_unit=None, **kwargs)`
- `restock_inventory(inventory_id, amount, unit_id, cost_per_unit, supplier=None)`
- `record_spoilage(inventory_id, amount, unit_id, reason=None)`

**Usage Examples:**
```python
# Restock ingredients
from app.services.inventory_adjustment import adjust_inventory

adjust_inventory(
    inventory_id=ingredient.id,
    amount=50,
    unit_id=unit.id,
    reason="restock",
    cost_per_unit=2.50,
    supplier="Supplier Name"
)
```

**Rules:**
- Creates inventory history entries for all changes
- Applies unit conversions automatically
- Integrates with FIFO service for deductions
- Maintains cost tracking and audit trails

### 3. Unit Conversion Service

**Class:** `ConversionEngine`
**Location:** `app/services/unit_conversion/unit_conversion.py`
**Drawer Mapping:** `app/services/unit_conversion/drawer_errors.py` (e.g., `MISSING_DENSITY`, `MISSING_CUSTOM_MAPPING`)

Handles all unit conversions with support for:
- Direct conversions (same unit type)
- Cross-type conversions (volume ↔ weight using density)
- Custom unit mappings
- Compound conversion paths

**Key Functions:**
- `convert_units(amount, from_unit_id, to_unit_id, ingredient_id=None)`
- `get_base_unit_amount(amount, unit_id)`
- `create_custom_mapping(from_unit_id, to_unit_id, multiplier, ingredient_id)`

**Usage Examples:**
```python
# Convert between units
from app.services.unit_conversion import convert_units

converted = convert_units(
    amount=100,
    from_unit_id=grams_unit.id,
    to_unit_id=kilograms_unit.id,
    ingredient_id=ingredient.id
)
```

**Rules:**
- Uses base units for all conversions
- Supports ingredient-specific density conversions
- Maintains custom unit mappings
- Validates conversion paths

### 4. Stock Check Service (package: `app/services/stock_check/`)

**Authority:** Real-time availability validation

**Key Modules:**
- Core logic: `app/services/stock_check/core.py`
- Handlers: `app/services/stock_check/handlers/*.py`

**Common Calls:**
- `check_recipe_availability(recipe_id, scale_factor=1.0)`
- `check_ingredient_availability(ingredient_id, required_amount, unit_id)`
- `get_available_inventory_summary()`

**Usage Examples:**
```python
# Check if recipe can be made
from app.services.stock_check.core import check_recipe_availability

availability = check_recipe_availability(
    recipe_id=recipe.id,
    scale_factor=2.0
)
```

**Rules:**
- Considers FIFO available quantities
- Accounts for reserved inventory
- Provides detailed shortage information
- Supports recipe scaling calculations
- Returns drawer payloads from dependent services when appropriate

### 5. Expiration Service (`app/blueprints/expiration/services.py`)

**Authority:** Shelf-life calculations and expiration alerts

### 6. Dashboard Alert Service (`app/services/dashboard_alerts.py`)

**Authority:** Unified alert management with cognitive load considerations

**Key Functions:**
- `get_dashboard_alerts(max_alerts=None, dismissed_alerts=None)`
- `get_alert_summary()`
- `_get_timer_alerts()`
- `_get_incomplete_batches()`

**Usage Examples:**
```python
# Get prioritized dashboard alerts
from app.services.dashboard_alerts import DashboardAlertService

alerts = DashboardAlertService.get_dashboard_alerts(max_alerts=3)
```

### 7. Combined Inventory Alert Service (`app/services/combined_inventory_alerts.py`)

**Authority:** Unified inventory alerting across expiration and stock levels

### 8. Billing Service (`app/services/billing_service.py`)

**Authority:** Stripe integration, subscription management, and tier enforcement

**Key Functions:**
- `get_live_pricing_for_tier(tier)` – retrieves and caches live Stripe pricing
- `create_checkout_session_for_tier(tier, ...)` – canonical checkout/session creation
- `handle_webhook_event(provider, event)` – idempotent webhook dispatcher
- `finalize_checkout_session(session_id)` – provisions organizations after checkout
- `create_customer_portal_session(organization, return_url)` – Stripe customer portal

**Notes:**
- Maintains the pending-signup lifecycle used by `/auth/signup`
- Consolidates all former `StripeService` logic into a single authority
- Exposes tier helpers (`get_tier_for_organization`, `validate_tier_access`, etc.) for middleware

### 9. Timer Service (`app/services/timer_service.py`)

**Authority:** Production timer management

### 10. Product Service (`app/services/product_service.py`)

**Authority:** Product lifecycle and variant management

**Key Functions:**
- `calculate_batch_expiration(batch_id)`
- `get_expiring_inventory(days_ahead=7)`
- `mark_inventory_expired(inventory_id)`

**Usage Examples:**
```python
# Check expiring inventory
from app.blueprints.expiration.services import get_expiring_inventory

expiring = get_expiring_inventory(days_ahead=14)
```

**Rules:**
- Calculates earliest expiration from ingredients
- Generates proactive expiration alerts
- Handles batch-level shelf-life inheritance
- Supports custom expiration overrides

## Supporting Services

### 6. Statistics Service (modular)

**Authority:** User and organization statistics

**Key Modules:**
- `app/services/statistics/_core.py`
- `app/services/statistics/_batch_stats.py`
- `app/services/statistics/_inventory_stats.py`
- `app/services/statistics/_recipe_stats.py`

**Usage Examples:**
```python
from app.services.statistics import StatisticsService

stats = StatisticsService.get_organization_dashboard_stats(org_id)
```

### 7. Reservation Service (`app/services/reservation_service.py`)

**Authority:** Inventory reservations for pending orders

**Key Functions:**
- `create_reservation(product_sku_id, quantity, customer_info)`
- `release_reservation(reservation_id)`
- `convert_to_sale(reservation_id)`

**Usage Examples:**
```python
# Reserve product for customer
from app.services.reservation_service import create_reservation

reservation = create_reservation(
    product_sku_id=sku.id,
    quantity=5,
    customer_info={"name": "John Doe"}
)
```

### 8. Recipe Marketplace Service (`app/services/recipe_marketplace_service.py`)

**Authority:** Recipe sharing metadata (private/public/sale), Shopify links, cover images, and marketplace payload normalization.

**Key Responsibilities:**
- Normalize marketplace form fields before `create_recipe`/`update_recipe`.
- Persist product group selection, sharing scope, sale price, and notes.
- Validate and store cover images under `static/product_images/recipes`.
- Preserve existing marketplace attributes when the feature flag is disabled.

**Usage Example:**
```python
from app.services.recipe_marketplace_service import RecipeMarketplaceService

ok, payload = RecipeMarketplaceService.extract_submission(request.form, request.files, existing=recipe)
if not ok:
    flash(payload, "error")
marketplace_kwargs = payload["marketplace"]
cover_kwargs = payload["cover"]
```

**Rules:**
- Only accepts PNG/JPG/GIF/WEBP covers; everything else raises `ValueError`.
- Does not mutate existing marketplace state when fields are omitted (e.g., feature disabled).
- Always returns both marketplace kwargs and cover kwargs so routes stay thin.
- Provides the canonical path for toggling public vs private, free vs sale, seeding product groups, saving Shopify URLs, and uploading cover imagery.

## Service Integration Patterns

### 1. Batch Production Flow (PlanSnapshot → Start → Finish)
```python
# 1) Plan (server-side)
from app.services.production_planning.service import PlanProductionService

plan = PlanProductionService.build_plan(
    recipe=recipe,          # frozen from DB
    scale=2.0,              # user-selected
    batch_type='product',   # user-selected
    notes='',               # optional, not persisted at start
    containers=[{'id': 11, 'quantity': 4}]
)

# 2) Start (API)
# Client submits the exact plan as a DTO
resp = POST /batches/api/start-batch { 'plan_snapshot': plan }

# 3) Start (service)
# - Persists batch.projected_yield/unit, portioning, plan_snapshot
# - Creates BatchIngredient/BatchConsumable via Conversion + Inventory Adjustment
# - Creates BatchContainer via Inventory Adjustment

# 4) Finish
# - Record final_quantity/unit, final_portions (if portioned)
# - Create product/ingredient outputs
```

### 2. Inventory Management Flow
```python
# 1. Restock with cost tracking
adjust_inventory(
    inventory_id=ingredient.id,
    amount=quantity,
    unit_id=unit.id,
    reason="restock",
    cost_per_unit=cost,
    supplier=supplier_name
)

# 2. Handle spoilage
adjust_inventory(
    inventory_id=ingredient.id,
    amount=-spoiled_amount,
    unit_id=unit.id,
    reason="spoil",
    notes="Found mold"
)
```

## Error Handling

### Service-Level Exceptions
- `InsufficientInventoryError` - Not enough stock available
- `UnitConversionError` - Cannot convert between units
- `InvalidPermissionError` - User lacks required permissions
- `OrganizationScopeError` - Cross-organization data access

### Error Response Patterns
```python
result = service_function(**params)
if result.get('drawer_payload'):
    return {"success": False, **result}
return {"success": True, "data": result}
```

## Testing Services

### Unit Test Examples
```python
def test_fifo_deduction():
    # Test FIFO service deduction logic
    result = deduct_inventory_fifo(
        inventory_id=test_inventory.id,
        amount=100,
        unit_id=grams_unit.id,
        reason="test"
    )
    assert result.success
    assert result.deducted_amount == 100
```

### Integration Test Examples
```python
def test_batch_production_flow():
    # Test full batch production with services
    availability = check_recipe_availability(recipe.id)
    assert availability.can_make

    batch = start_batch(recipe.id, scale_factor=1.0)
    assert batch.status == "in_progress"

    finished_batch = finish_batch(batch.id, actual_yield=500)
    assert finished_batch.status == "completed"
```

## Performance Optimization

### Service Caching
- Unit conversion cache for repeated calculations
- Stock check cache for production planning
- Permission cache for user sessions

### Database Optimization
- Service queries optimized for organization scoping
- Indexes on frequently queried service parameters
- Batch processing for bulk operations

---

**Next:** See [USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md) for user management details. Also see [WALL_OF_DRAWERS_PROTOCOL.md](WALL_OF_DRAWERS_PROTOCOL.md).