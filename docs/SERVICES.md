
# BatchTrack Services Documentation

## Service Overview

BatchTrack uses a service-oriented architecture where each service has complete authority over its domain. **Never bypass these services** - always use the proper service for any operation in its domain.

## Core Services

### 1. FIFO Service (`app/blueprints/fifo/services.py`)

**Authority:** All inventory deduction order and batch lot management

**Key Functions:**
- `deduct_inventory_fifo(inventory_id, amount, unit_id, reason, batch_id=None)`
- `get_fifo_details(inventory_id)`
- `get_available_quantity(inventory_id)`

**Usage Examples:**
```python
# Deduct ingredients for batch production
from app.blueprints.fifo.services import deduct_inventory_fifo

result = deduct_inventory_fifo(
    inventory_id=ingredient.inventory_id,
    amount=required_amount,
    unit_id=ingredient.unit_id,
    reason="batch",
    batch_id=batch.id
)
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

### 3. Unit Conversion Service (`app/services/unit_conversion.py`)

**Authority:** All unit conversions and custom unit mappings

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

### 4. Stock Check Service (`app/services/stock_check.py`)

**Authority:** Real-time availability validation

**Key Functions:**
- `check_recipe_availability(recipe_id, scale_factor=1.0)`
- `check_ingredient_availability(ingredient_id, required_amount, unit_id)`
- `get_available_inventory_summary()`

**Usage Examples:**
```python
# Check if recipe can be made
from app.services.stock_check import check_recipe_availability

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

### 5. Expiration Service (`app/blueprints/expiration/services.py`)

**Authority:** Shelf-life calculations and expiration alerts

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

### 6. Statistics Service (`app/services/statistics_service.py`)

**Authority:** User and organization statistics

**Key Functions:**
- `get_user_statistics(user_id)`
- `get_organization_statistics(organization_id)`
- `update_batch_statistics(user_id, organization_id)`

**Usage Examples:**
```python
# Get user stats
from app.services.statistics_service import get_user_statistics

stats = get_user_statistics(current_user.id)
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

## Service Integration Patterns

### 1. Batch Production Flow
```python
# 1. Check availability
availability = check_recipe_availability(recipe_id, scale_factor)

# 2. Reserve ingredients (optional)
reservations = create_ingredient_reservations(recipe_id, batch_id)

# 3. Start batch and deduct ingredients
for ingredient in recipe.ingredients:
    deduct_inventory_fifo(
        inventory_id=ingredient.inventory_id,
        amount=ingredient.amount * scale_factor,
        unit_id=ingredient.unit_id,
        reason="batch",
        batch_id=batch.id
    )

# 4. Finish batch and add products
adjust_inventory(
    inventory_id=product.inventory_id,
    amount=batch.actual_yield,
    unit_id=product.unit_id,
    reason="finished_batch",
    batch_id=batch.id
)
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
try:
    result = service_function(**params)
    return {"success": True, "data": result}
except ServiceError as e:
    return {"success": False, "error": str(e)}
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

**Next:** See [USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md) for user management details.
