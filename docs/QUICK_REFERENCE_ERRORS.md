# Error Handling - Quick Reference Card

## Import Pattern

```python
from app.utils.error_messages import ErrorMessages as EM
from app.utils.error_messages import SuccessMessages as SM
from app.utils.error_messages import WarningMessages as WM
from app.utils.api_responses import APIResponse
```

---

## Flash Messages (HTML Routes)

```python
# Error (red alert)
flash(EM.INVENTORY_NOT_FOUND, 'error')

# Success (green alert)
flash(SM.RECIPE_CREATED, 'success')

# Warning (yellow alert)
flash(WM.BATCH_STARTED_WITH_WARNINGS.format(warnings=details), 'warning')

# Info (blue alert)
flash(IM.FEATURE_COMING_SOON.format(feature='Export'), 'info')

# With parameters
flash(EM.PERMISSION_DENIED.format(permission='inventory.edit'), 'error')
```

---

## API Responses (JSON Routes)

### Success Response (200)
```python
return APIResponse.success(
    data={'id': 123, 'name': 'Item'},
    message=SM.OPERATION_SUCCESSFUL
)
```

### Created Response (201)
```python
return APIResponse.success(
    data=new_item.to_dict(),
    message=SM.ITEM_CREATED,
    status_code=201
)
```

### Error Response (400)
```python
return APIResponse.error(
    message=EM.VALIDATION_FAILED,
    errors={'field': 'name', 'issue': 'required'},
    status_code=400
)
```

### Not Found (404)
```python
return APIResponse.error(
    message=EM.ITEM_NOT_FOUND,
    errors={'item_id': item_id},
    status_code=404
)
```

### Forbidden (403)
```python
return APIResponse.error(
    message=EM.PERMISSION_DENIED.format(permission='feature.edit'),
    status_code=403
)
```

### Server Error (500)
```python
logger.exception(f"Error: {str(e)}")
return APIResponse.error(
    message=EM.SYSTEM_ERROR,
    status_code=500
)
```

---

## Common Patterns

### Not Found Check
```python
item = Model.query.get(item_id)
if not item:
    # HTML
    flash(EM.ITEM_NOT_FOUND, 'error')
    return redirect(url_for('feature.list'))
    
    # API
    return APIResponse.error(
        message=EM.ITEM_NOT_FOUND,
        errors={'item_id': item_id},
        status_code=404
    )
```

### Validation Error
```python
if not name:
    # HTML
    flash(EM.VALIDATION_REQUIRED_FIELDS.format(fields='name'), 'error')
    return redirect(request.referrer)
    
    # API
    return APIResponse.error(
        message=EM.VALIDATION_REQUIRED_FIELDS.format(fields='name'),
        errors={'missing_fields': ['name']},
        status_code=400
    )
```

### Permission Check
```python
if not has_permission('feature.edit'):
    # HTML
    flash(EM.PERMISSION_DENIED.format(permission='feature.edit'), 'error')
    return redirect(url_for('app_routes.dashboard'))
    
    # API
    return APIResponse.error(
        message=EM.PERMISSION_DENIED.format(permission='feature.edit'),
        status_code=403
    )
```

### System Error
```python
try:
    # Operation
except Exception as e:
    logger.exception(f"Error in operation: {str(e)}")
    
    # HTML
    flash(EM.SYSTEM_ERROR, 'error')
    return redirect(url_for('safe_page'))
    
    # API
    return APIResponse.error(
        message=EM.SYSTEM_ERROR,
        status_code=500
    )
```

---

## Adding New Messages

### 1. Open error_messages.py
```bash
# Edit the file
vim app/utils/error_messages.py
```

### 2. Add Your Message
```python
class ErrorMessages:
    # Find appropriate section
    # ==================== YOUR FEATURE ====================
    FEATURE_NOT_FOUND = "Feature not found."
    FEATURE_CREATE_FAILED = "Failed to create feature: {reason}"
    FEATURE_INVALID_STATUS = "Feature must be {required}, not {current}"

class SuccessMessages:
    # ==================== YOUR FEATURE ====================
    FEATURE_CREATED = "Feature created successfully."
```

### 3. Use In Your Code
```python
from app.utils.error_messages import ErrorMessages as EM
flash(EM.FEATURE_CREATE_FAILED.format(reason='Duplicate name'), 'error')
```

---

## Status Codes

- **200** - Success (GET, PUT, PATCH)
- **201** - Created (POST)
- **400** - Bad Request (validation error)
- **403** - Forbidden (permission denied)
- **404** - Not Found
- **500** - Server Error (unexpected)

---

## Message Format Rules

✅ **DO:**
- Use plain text only
- Use `{placeholder}` for dynamic values
- End sentences with periods
- Keep user-friendly (not too technical)
- Group by feature/module

❌ **DON'T:**
- Include HTML tags
- Use f-strings in constants
- Expose internal errors
- Make messages too long
- Create duplicate messages

---

## Testing

```python
def test_error_message():
    from app.utils.error_messages import ErrorMessages as EM
    
    response = client.get('/api/items/99999')
    data = response.get_json()
    
    assert response.status_code == 404
    assert data['message'] == EM.ITEM_NOT_FOUND
```

---

## Full Example

```python
from flask import Blueprint, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.utils.error_messages import ErrorMessages as EM, SuccessMessages as SM
from app.utils.api_responses import APIResponse
from app.services.feature_service import FeatureService
import logging

logger = logging.getLogger(__name__)

feature_bp = Blueprint('features', __name__)

@feature_bp.route('/api/features/<int:feature_id>', methods=['GET'])
@login_required
def api_get_feature(feature_id):
    """Get feature by ID"""
    try:
        feature = FeatureService.get_by_id(feature_id)
        
        if not feature:
            return APIResponse.error(
                message=EM.FEATURE_NOT_FOUND,
                errors={'feature_id': feature_id},
                status_code=404
            )
        
        return APIResponse.success(
            data=feature.to_dict(),
            message="Feature retrieved successfully"
        )
        
    except Exception as e:
        logger.exception(f"Error getting feature {feature_id}: {str(e)}")
        return APIResponse.error(
            message=EM.SYSTEM_ERROR,
            errors={'feature_id': feature_id},
            status_code=500
        )
```

---

## Available Message Categories

### ErrorMessages (EM)
- Authentication & Authorization
- Organization
- Inventory
- Recipes
- Batches
- Products & SKUs
- Reservations
- Timers
- Units & Conversion
- Expiration
- Stock Check
- Billing & Subscriptions
- Settings & Preferences
- Validation
- System

### SuccessMessages (SM)
- All successful operations

### WarningMessages (WM)
- Non-critical issues

### InfoMessages (IM)
- Informational notices

See `app/utils/error_messages.py` for complete list.
