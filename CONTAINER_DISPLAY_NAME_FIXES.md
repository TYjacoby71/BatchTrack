# Container Display Name Fixes

## Summary
Updated the codebase to use the new `container_display_name` property instead of the raw `name` field for containers. This ensures that containers are displayed using their structured attributes (type, style, material) instead of just the raw name.

## Background
The container inventory system was updated to include structured fields:
- `container_style` (e.g., "Boston Round", "Straight Sided")
- `container_material` (e.g., "Glass", "Plastic")
- `container_shape` (e.g., "Bottle", "Jar")
- `container_color` (optional)

The `container_display_name` property (defined in `InventoryItem` model) automatically computes a clean display name from these structured attributes, avoiding duplication and following naming conventions.

## Files Modified

### 1. Production Planning - Container Management
**File:** `app/services/production_planning/_container_management.py`
- **Line 145-149:** Added logic to use `container.container_display_name` when building container options
- **Impact:** Plan production page now shows properly formatted container names

### 2. Production Planning Routes
**File:** `app/blueprints/production_planning/routes.py`
- **Line 142-143:** Updated debug endpoint to use `container_display_name`
- **Impact:** Debug/diagnostic views show correct container names

### 3. Stock Check Handler
**File:** `app/services/stock_check/handlers/container_handler.py`
- **Lines 47-48:** Updated logging to show container display names
- **Line 58:** Updated container selection display
- **Line 99:** Updated result display name
- **Line 133:** Updated error result display name
- **Line 156:** Updated get_item_details to return display name
- **Line 222:** Updated check_stock result display name
- **Impact:** Stock checking now displays containers correctly

### 4. Batch Starting
**File:** `app/blueprints/batches/start_batch.py`
- **Line 72-73:** Updated deduction summary to show container display names
- **Impact:** Batch start messages show correct container names

### 5. Batch Operations
**File:** `app/services/batch_service/batch_operations.py`
- **Lines 461-462:** Updated container restoration summary (regular containers)
- **Lines 476-477:** Updated container restoration summary (extra containers)
- **Impact:** Batch cancellation messages show correct container names

### 6. FIFO API Routes
**File:** `app/blueprints/api/fifo_routes.py`
- **Lines 94-96:** Updated regular container summary in API response
- **Lines 101-103:** Updated extra container summary in API response
- **Impact:** API responses return properly formatted container names

### 7. Batch Integration Service
**File:** `app/services/batch_integration_service.py`
- **Lines 87-89:** Updated regular container info display
- **Lines 100-102:** Updated extra container info display
- **Impact:** Batch integration displays correct container names

## Product SKU Creation
**File:** `app/blueprints/batches/finish_batch.py`
- **Already Updated:** The `_create_container_sku` function (lines 509-519) was already using `container_display_name`
- **Status:** ✅ No changes needed - already implemented correctly

## Pattern Used
All updates follow this pattern:
```python
# For containers, use computed display name
container_display = container.container_display_name if container.type == 'container' else container.name
```

This ensures backward compatibility with non-container inventory items while properly displaying containers with their structured attributes.

## Testing Recommendations
1. Create a test container with style="Boston Round", material="Glass", shape="Bottle"
2. Add this container to a recipe's allowed containers
3. Navigate to the plan production page
4. Verify the container appears as "Boston Round Glass Bottle" (or "Boston Round Bottle" if material is in style/shape)
5. Test container selection in auto-fill and manual modes
6. Start and finish a batch with containers
7. Verify all messages and displays show the correct formatted name

## Impact
- ✅ Plan production page can now find and display containers correctly
- ✅ Product SKU creation uses proper container names
- ✅ All container-related messages and logs show formatted names
- ✅ API responses include properly formatted container names
- ✅ Backward compatible with containers that don't have structured attributes
