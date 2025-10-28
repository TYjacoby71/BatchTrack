# Error Message Clarity Audit Report

## Summary
This audit identifies generic error messages in the codebase that need to be improved with specific, actionable context and details.

**Status**: ✅ **GOOD NEWS - Most errors already have good context!**

The codebase already uses many best practices:
- ✅ `APIResponse.error()` utility exists in `app/utils/api_responses.py`
- ✅ Drawer error patterns exist in `app/services/unit_conversion/drawer_errors.py`
- ✅ Most service-level code provides detailed error context
- ❌ Only **route-level** error handlers have some generic messages

---

## Issues Found

### 1. Timer Routes (`app/blueprints/timers/routes.py`)
**Severity**: LOW (service failures, not common use cases)

#### Line 106: Generic stop timer error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to stop timer'}), 400

# RECOMMENDED
from app.utils.api_responses import APIResponse

return APIResponse.error(
    message='Cannot stop timer',
    errors={
        'timer_id': timer_id,
        'current_status': timer.status,
        'reason': 'Timer may already be stopped or in an invalid state',
        'suggestion': 'Check the timer status before attempting to stop it.'
    },
    status_code=400
)
```

#### Line 140: Generic pause timer error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to pause timer'}), 400

# RECOMMENDED
return APIResponse.error(
    message='Cannot pause timer',
    errors={
        'timer_id': timer_id,
        'current_status': timer.status,
        'reason': 'Timer can only be paused when active',
        'suggestion': 'Only active timers can be paused.'
    },
    status_code=400
)
```

#### Line 154: Generic resume timer error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to resume timer'}), 400

# RECOMMENDED
return APIResponse.error(
    message='Cannot resume timer',
    errors={
        'timer_id': timer_id,
        'current_status': timer.status,
        'reason': 'Timer can only be resumed when paused',
        'suggestion': 'Only paused timers can be resumed.'
    },
    status_code=400
)
```

---

### 2. Product Inventory Routes (`app/blueprints/products/product_inventory_routes.py`)
**Severity**: MEDIUM (user-facing operations)

#### Line 326: Generic dispose expired inventory error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to dispose expired inventory'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to dispose expired inventory',
    errors={
        'sku_id': sku_id,
        'sku_name': sku.display_name if sku else 'Unknown',
        'expired_quantity': total_expired if 'total_expired' in locals() else 'Unknown',
        'reason': str(e) if 'e' in locals() else 'System error during disposal operation',
        'suggestion': 'Check if the SKU has expired inventory lots and try again.'
    },
    status_code=500
)
```

#### Line 379: Generic process sale error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to process sale'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to process sale',
    errors={
        'sku_code': data.get('sku_code'),
        'quantity': data.get('quantity'),
        'available_quantity': sku.quantity if sku else None,
        'reason': str(e) if 'e' in locals() else 'Inventory deduction failed',
        'suggestion': 'Verify sufficient inventory is available before processing sale.'
    },
    status_code=500
)
```

#### Line 431: Generic process return error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to process return'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to process return',
    errors={
        'sku_code': data.get('sku_code'),
        'quantity': data.get('quantity'),
        'reason': str(e) if 'e' in locals() else 'Inventory adjustment failed',
        'suggestion': 'Verify the return information and try again.'
    },
    status_code=500
)
```

#### Line 490: Generic create reservation error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to create reservation'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to create reservation',
    errors={
        'inventory_item_id': inventory_item_id,
        'quantity': quantity,
        'order_id': order_id,
        'reason': str(e) if 'e' in locals() else 'Reservation creation failed',
        'suggestion': 'Verify sufficient inventory is available and all required fields are provided.'
    },
    status_code=500
)
```

#### Line 558: Generic add inventory error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to add inventory'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to add inventory from batch',
    errors={
        'batch_id': batch_id,
        'product_name': product_name,
        'quantity': quantity,
        'reason': str(e) if 'e' in locals() else 'Inventory addition failed',
        'suggestion': 'Verify the batch is finished and the SKU information is correct.'
    },
    status_code=500
)
```

---

### 3. Batch Start (`app/blueprints/batches/start_batch.py`)
**Severity**: MEDIUM (user-facing operation)

#### Line 61: Generic start batch error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to start batch'}), 400

# RECOMMENDED
# NOTE: The errors variable already contains detailed error information from the service
# This should be enhanced to return those details

return APIResponse.error(
    message='Failed to start batch',
    errors={
        'recipe_id': recipe_id,
        'scale': scale,
        'details': errors,  # errors already contains specific failure details
        'suggestion': 'Check inventory availability and recipe configuration.'
    },
    status_code=400
)
```

---

### 4. Reservation API (`app/blueprints/api/reservation_routes.py`)
**Severity**: MEDIUM (API operations)

#### Line 76: Generic create reservation error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to create reservation'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to create reservation',
    errors={
        'sku_code': data.get('sku_code'),
        'quantity': data.get('quantity'),
        'order_id': data.get('order_id'),
        'available_quantity': sku.quantity if sku else None,
        'reason': str(e),
        'suggestion': 'Verify sufficient inventory is available for reservation.'
    },
    status_code=500
)
```

#### Line 104: Generic release reservation error
```python
# CURRENT (BAD)
return jsonify({'error': 'Failed to release reservation'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Failed to release reservation',
    errors={
        'reservation_id': reservation_id,
        'reason': str(e) if 'e' in locals() else 'Reservation release operation failed',
        'suggestion': 'Verify the reservation exists and is in a releasable state.'
    },
    status_code=500
)
```

---

### 5. Billing Routes (`app/blueprints/billing/routes.py`)
**Severity**: LOW (webhook processing, not user-facing)

#### Lines 552, 574: Generic processing failed error
```python
# CURRENT (BAD)
return jsonify({'error': 'Processing failed'}), 500

# RECOMMENDED
return APIResponse.error(
    message='Webhook processing failed',
    errors={
        'event_type': event.get('type') if 'event' in locals() else 'Unknown',
        'customer_id': customer_id if 'customer_id' in locals() else None,
        'reason': str(e),
        'suggestion': 'Check Stripe webhook logs for details.'
    },
    status_code=500
)
```

---

## Already Good Examples

### ✅ Unit Conversion Errors
The `app/services/unit_conversion/drawer_errors.py` already handles conversion errors well:
- Provides specific error codes (MISSING_DENSITY, MISSING_CUSTOM_MAPPING, etc.)
- Includes detailed context (from_unit, to_unit, ingredient info)
- Suggests actionable fixes (add density, create mapping)

### ✅ Inventory Routes
The `app/blueprints/inventory/routes.py` uses the centralized service which already provides detailed errors:
- Specific validation messages
- Context about what failed and why
- Proper error handling at service level

### ✅ Conversion Routes
The `app/blueprints/conversion/routes.py` at line 27-32 shows good error handling:
```python
return jsonify({
    'converted_value': None,
    'conversion_type': 'error',
    'message': str(e),  # Detailed message from exception
    'requires_attention': True
}), 400
```

---

## Recommendations

### Priority 1: Product Inventory Routes (MEDIUM Impact)
Fix the 5 generic errors in `app/blueprints/products/product_inventory_routes.py`:
- Lines 326, 379, 431, 490, 558
- These are user-facing operations (sales, returns, reservations)
- Should provide specific context about what inventory item, quantity, and why it failed

### Priority 2: Batch Start Route (MEDIUM Impact)  
Fix the generic error in `app/blueprints/batches/start_batch.py`:
- Line 61
- Already has `errors` variable with details - just need to pass it through
- Critical user operation that needs clear feedback

### Priority 3: Reservation API (MEDIUM Impact)
Fix the 2 generic errors in `app/blueprints/api/reservation_routes.py`:
- Lines 76, 104
- API endpoints need structured error responses

### Priority 4: Timer Routes (LOW Impact)
Fix the 3 generic errors in `app/blueprints/timers/routes.py`:
- Lines 106, 140, 154
- Less critical - timer operations are secondary features

### Priority 5: Billing Webhooks (LOW Impact)
Fix the 2 generic errors in `app/blueprints/billing/routes.py`:
- Lines 552, 574
- Backend webhooks - not directly user-facing

---

## Implementation Pattern

### Standard Pattern to Use:
```python
from app.utils.api_responses import APIResponse

# Instead of:
return jsonify({'error': 'Failed to do X'}), 400

# Use:
return APIResponse.error(
    message='Specific description of what failed',
    errors={
        'field1': 'value or context',
        'field2': 'value or context',
        'reason': 'Why it failed',
        'suggestion': 'What the user should do next'
    },
    status_code=400
)
```

### For Drawer Responses (Interactive Fixes):
```python
from app.services.unit_conversion.drawer_errors import handle_conversion_error

# When conversion fails with fixable issues:
result = handle_conversion_error(conversion_result)
if result.get('requires_drawer'):
    return jsonify({
        'success': False,
        'drawer_type': result['drawer_type'],
        'drawer_data': result['drawer_data'],
        'message': result['error_message']
    }), 400
```

---

## Total Issues Found

| File | Generic Errors | Severity | Priority |
|------|---------------|----------|----------|
| timers/routes.py | 3 | LOW | P4 |
| products/product_inventory_routes.py | 5 | MEDIUM | P1 |
| batches/start_batch.py | 1 | MEDIUM | P2 |
| api/reservation_routes.py | 2 | MEDIUM | P3 |
| billing/routes.py | 2 | LOW | P5 |
| **TOTAL** | **13** | | |

---

## Estimated Effort

- **Per file**: 30-45 minutes to fix all errors
- **Total time**: 2-3 hours for all 13 errors
- **Testing**: Additional 1 hour for testing fixes

**Total Estimated Time**: 3-4 hours

---

## Next Steps

1. ✅ Audit completed - 13 generic error messages identified
2. ⏳ Fix Priority 1: Product Inventory Routes (5 errors)
3. ⏳ Fix Priority 2: Batch Start Route (1 error)
4. ⏳ Fix Priority 3: Reservation API (2 errors)
5. ⏳ Fix Priority 4: Timer Routes (3 errors)
6. ⏳ Fix Priority 5: Billing Routes (2 errors)
7. ⏳ Test all fixed error messages
8. ⏳ Update any affected frontend error handlers

---

## Notes

- The existing `APIResponse.error()` utility in `app/utils/api_responses.py` is well-designed
- Most service-layer code already provides detailed errors
- The issues are primarily in route-level exception handlers
- The drawer error pattern in `unit_conversion/drawer_errors.py` is exemplary
- Frontend already expects structured error responses with `errors` object
