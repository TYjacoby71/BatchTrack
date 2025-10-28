# Container Type vs Shape Field Name Fix

## The Issue

There was a critical field name discrepancy between two models:

### Database Schema (from migrations)
- **GlobalItem table**: Uses `container_type` column
- **InventoryItem table**: Uses `container_shape` column

### Model Definitions
- **GlobalItem model**: Uses `container_type` field ✅ Correct
- **InventoryItem model**: Uses `container_shape` field ✅ Correct

### The Bug
The inventory adjustment services were incorrectly trying to set `container_type` on InventoryItem objects, but that field doesn't exist! InventoryItem uses `container_shape`.

## Why Two Different Field Names?

This is intentional design:

- **GlobalItem.container_type**: Global library uses "type" to represent the base container category (e.g., "Bottle", "Jar", "Tube")
- **InventoryItem.container_shape**: Organization inventory uses "shape" to represent the physical form

The semantic difference:
- `container_type` = Category/classification concept
- `container_shape` = Physical descriptor concept

Both refer to the same thing (Bottle, Jar, etc.) but from different perspectives.

## Files Fixed

### 1. Creation Logic - FIXED ✅
**File:** `app/services/inventory_adjustment/_creation_logic.py`

**Line 148 - Direct Form Input:**
```python
# BEFORE (WRONG)
new_item.container_type = ctype or None

# AFTER (CORRECT)
new_item.container_shape = ctype or None  # InventoryItem uses container_shape
```

**Line 170 - Copying from GlobalItem:**
```python
# BEFORE (WRONG)
if getattr(global_item, 'container_type', None):
    new_item.container_type = global_item.container_type

# AFTER (CORRECT)
if getattr(global_item, 'container_type', None):
    # GlobalItem has container_type, InventoryItem has container_shape
    new_item.container_shape = global_item.container_type
```

### 2. Edit Logic - FIXED ✅
**File:** `app/services/inventory_adjustment/_edit_logic.py`

**Line 112:**
```python
# BEFORE (WRONG)
if 'container_type' in form_data:
    item.container_type = (form_data.get('container_type') or '').strip() or None

# AFTER (CORRECT)
if 'container_type' in form_data:
    # InventoryItem uses container_shape field (not container_type like GlobalItem)
    item.container_shape = (form_data.get('container_type') or '').strip() or None
```

## Form Field Naming Convention

**Important**: Form fields continue to use `container_type` as the field name for consistency across the UI. The backend then maps this to the correct model field:

```
Form Field Name     → Backend Model Field
----------------------------------------
container_material  → InventoryItem.container_material (same)
container_type      → InventoryItem.container_shape (mapped!)
container_style     → InventoryItem.container_style (same)
container_color     → InventoryItem.container_color (same)
```

This keeps the UI/API consistent while properly handling the different field names in the models.

## Container Display Name Property

The `container_display_name` property in InventoryItem correctly uses `container_shape`:

```python
@property
def container_display_name(self):
    """Derived clean display name from structured attributes."""
    if self.type != 'container':
        return self.name
    
    style = (self.container_style or '').strip()
    material = (self.container_material or '').strip()
    base_type = (self.container_shape or '').strip()  # ← Correctly uses container_shape
    
    # ... assembly logic ...
```

## Files That Correctly Use container_type (No Changes Needed)

### Developer Routes - GlobalItem Management
**File:** `app/blueprints/developer/routes.py`

Lines 693, 726, 879-880, 1185 all work with **GlobalItem** objects, so they correctly use `container_type`.

### Seed Scripts
**File:** `scripts/seed_containers.py`

Creates **GlobalItem** objects, correctly uses `container_type`.

## Summary of Field Usage

| Context | Model | Field Name |
|---------|-------|------------|
| Global Library | GlobalItem | `container_type` |
| Organization Inventory | InventoryItem | `container_shape` |
| Form/API Field Name | (interface) | `container_type` |
| Display Property Uses | InventoryItem | `container_shape` |

## Mapping Flow

When creating an InventoryItem from a GlobalItem:

```python
# GlobalItem → InventoryItem mapping
global_item.container_material  →  new_item.container_material  ✅
global_item.container_type      →  new_item.container_shape     ✅ (mapped)
global_item.container_style     →  new_item.container_style     ✅
global_item.container_color     →  new_item.container_color     ✅
```

## Testing Recommendations

1. Create a new container from the global library with:
   - container_type = "Bottle"
   - container_material = "Glass"
   - container_style = "Boston Round"

2. Verify the InventoryItem is created with:
   - container_shape = "Bottle"
   - container_material = "Glass"
   - container_style = "Boston Round"

3. Verify `container_display_name` returns: "Boston Round Glass Bottle"

4. Edit the container and verify changes persist correctly

5. Use the container in a recipe and verify it displays correctly in production planning

## Impact

✅ Container creation from global library now works correctly  
✅ Container editing now works correctly  
✅ Container display names use the correct field  
✅ No changes needed to forms/API (field name consistency maintained)  
✅ No changes needed to GlobalItem management (already correct)  

## Migration Status

**No database migration needed** - The database schema is already correct:
- `global_item.container_type` exists ✅
- `inventory_item.container_shape` exists ✅

Only the Python code needed fixing to properly map between these fields.
