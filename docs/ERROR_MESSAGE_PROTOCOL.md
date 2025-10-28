# Error Message Protocol

## Overview

This document defines the standard protocol for error handling and messaging across the BatchTrack application. All developers must follow these guidelines when adding new routes, services, or features.

---

## Core Principles

1. **Centralized Messages** - All user-facing messages live in `app/utils/error_messages.py`
2. **Consistent Categorization** - Use flash categories: `error`, `success`, `warning`, `info`
3. **No HTML in Messages** - All messages are plain text (Jinja2 handles escaping)
4. **Structured API Responses** - Use `APIResponse` class for JSON endpoints
5. **Context Over Generic** - Provide specific details about what went wrong

---

## Quick Reference

### Import Pattern
```python
from app.utils.error_messages import ErrorMessages as EM
from app.utils.error_messages import SuccessMessages as SM
from app.utils.error_messages import WarningMessages as WM
from app.utils.error_messages import InfoMessages as IM
from app.utils.api_responses import APIResponse
```

### Flash Messages (HTML Routes)
```python
flash(EM.INVENTORY_NOT_FOUND, 'error')
flash(SM.RECIPE_CREATED, 'success')
flash(WM.BATCH_STARTED_WITH_WARNINGS.format(warnings=details), 'warning')
```

### API Responses (JSON Endpoints)
```python
return APIResponse.error(
    message=EM.INVENTORY_NOT_FOUND,
    errors={'inventory_id': item_id},
    status_code=404
)
```

---

## Adding a New Feature (Step-by-Step)

### Step 1: Define Your Error Messages

Before writing any route logic, add your messages to `app/utils/error_messages.py`:

```python
# app/utils/error_messages.py

class ErrorMessages:
    # ... existing messages ...
    
    # ==================== YOUR NEW FEATURE ====================
    FEATURE_NOT_FOUND = "Feature not found."
    FEATURE_CREATE_FAILED = "Failed to create feature: {reason}"
    FEATURE_UPDATE_FAILED = "Failed to update feature: {reason}"
    FEATURE_DELETE_FAILED = "Failed to delete feature: {reason}"
    FEATURE_INVALID_STATUS = "Feature must be in '{required_status}' status. Current status: {current_status}"
    FEATURE_PERMISSION_REQUIRED = "You need '{permission}' permission to perform this action."
    FEATURE_VALIDATION_FAILED = "{field} is required and cannot be empty."

class SuccessMessages:
    # ... existing messages ...
    
    # ==================== YOUR NEW FEATURE ====================
    FEATURE_CREATED = "Feature created successfully."
    FEATURE_UPDATED = "Feature updated successfully."
    FEATURE_DELETED = "Feature deleted successfully."
    FEATURE_ACTION_COMPLETED = "{action} completed successfully for {name}."
```

**Guidelines:**
- Group related messages together
- Use SCREAMING_SNAKE_CASE for constants
- Use `{placeholders}` for dynamic content
- Keep messages user-friendly (not too technical)
- End error messages with a period
- Start with the problem, then context

### Step 2: Create Your Route File

Follow the standard route structure:

```python
# app/blueprints/features/routes.py

from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.utils.permissions import require_permission
from app.utils.error_messages import ErrorMessages as EM, SuccessMessages as SM
from app.utils.api_responses import APIResponse
from app.models import db, Feature
from app.services.feature_service import FeatureService
import logging

logger = logging.getLogger(__name__)

feature_bp = Blueprint('features', __name__, url_prefix='/features')


# ============================================================================
# HTML ROUTES (Return rendered templates)
# ============================================================================

@feature_bp.route('/')
@login_required
@require_permission('features.view')
def list_features():
    """List all features - HTML page"""
    try:
        features = FeatureService.get_all_features(
            organization_id=current_user.organization_id
        )
        return render_template('features/list.html', features=features)
    except Exception as e:
        logger.exception(f"Error listing features: {str(e)}")
        flash(EM.SYSTEM_ERROR, 'error')
        return redirect(url_for('app_routes.dashboard'))


@feature_bp.route('/<int:feature_id>')
@login_required
@require_permission('features.view')
def view_feature(feature_id):
    """View single feature - HTML page"""
    try:
        feature = FeatureService.get_feature(feature_id)
        if not feature:
            flash(EM.FEATURE_NOT_FOUND, 'error')
            return redirect(url_for('features.list_features'))
        
        return render_template('features/view.html', feature=feature)
    except Exception as e:
        logger.exception(f"Error viewing feature {feature_id}: {str(e)}")
        flash(EM.SYSTEM_ERROR, 'error')
        return redirect(url_for('features.list_features'))


@feature_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_permission('features.create')
def create_feature():
    """Create new feature - HTML form"""
    if request.method == 'GET':
        return render_template('features/form.html')
    
    try:
        # Validate required fields
        name = request.form.get('name', '').strip()
        if not name:
            flash(EM.FEATURE_VALIDATION_FAILED.format(field='Name'), 'error')
            return redirect(url_for('features.create_feature'))
        
        # Call service layer
        success, result = FeatureService.create_feature(
            name=name,
            description=request.form.get('description'),
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        
        if success:
            flash(SM.FEATURE_CREATED, 'success')
            return redirect(url_for('features.view_feature', feature_id=result.id))
        else:
            flash(EM.FEATURE_CREATE_FAILED.format(reason=result), 'error')
            return redirect(url_for('features.create_feature'))
            
    except Exception as e:
        logger.exception(f"Error creating feature: {str(e)}")
        flash(EM.FEATURE_CREATE_FAILED.format(reason=str(e)), 'error')
        return redirect(url_for('features.create_feature'))


# ============================================================================
# API ROUTES (Return JSON)
# ============================================================================

@feature_bp.route('/api/features', methods=['GET'])
@login_required
@require_permission('features.view')
def api_list_features():
    """List features - JSON API"""
    try:
        features = FeatureService.get_all_features(
            organization_id=current_user.organization_id
        )
        
        return APIResponse.success(
            data=[f.to_dict() for f in features],
            message="Features retrieved successfully"
        )
    except Exception as e:
        logger.exception(f"API error listing features: {str(e)}")
        return APIResponse.error(
            message=EM.SYSTEM_ERROR,
            status_code=500
        )


@feature_bp.route('/api/features/<int:feature_id>', methods=['GET'])
@login_required
@require_permission('features.view')
def api_get_feature(feature_id):
    """Get single feature - JSON API"""
    try:
        feature = FeatureService.get_feature(feature_id)
        
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
        logger.exception(f"API error getting feature {feature_id}: {str(e)}")
        return APIResponse.error(
            message=EM.SYSTEM_ERROR,
            errors={'feature_id': feature_id, 'error': str(e)},
            status_code=500
        )


@feature_bp.route('/api/features', methods=['POST'])
@login_required
@require_permission('features.create')
def api_create_feature():
    """Create feature - JSON API"""
    try:
        data = request.get_json()
        if not data:
            return APIResponse.error(
                message=EM.VALIDATION_JSON_REQUIRED,
                status_code=400
            )
        
        # Validate required fields
        name = data.get('name', '').strip()
        if not name:
            return APIResponse.error(
                message=EM.FEATURE_VALIDATION_FAILED.format(field='name'),
                errors={'field': 'name', 'provided': name},
                status_code=400
            )
        
        # Call service layer
        success, result = FeatureService.create_feature(
            name=name,
            description=data.get('description'),
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        
        if success:
            return APIResponse.success(
                data=result.to_dict(),
                message=SM.FEATURE_CREATED,
                status_code=201
            )
        else:
            return APIResponse.error(
                message=EM.FEATURE_CREATE_FAILED.format(reason=result),
                errors={'reason': result},
                status_code=400
            )
            
    except Exception as e:
        logger.exception(f"API error creating feature: {str(e)}")
        return APIResponse.error(
            message=EM.FEATURE_CREATE_FAILED.format(reason=str(e)),
            errors={'error': str(e)},
            status_code=500
        )


@feature_bp.route('/api/features/<int:feature_id>', methods=['PUT'])
@login_required
@require_permission('features.edit')
def api_update_feature(feature_id):
    """Update feature - JSON API"""
    try:
        feature = FeatureService.get_feature(feature_id)
        if not feature:
            return APIResponse.error(
                message=EM.FEATURE_NOT_FOUND,
                errors={'feature_id': feature_id},
                status_code=404
            )
        
        data = request.get_json()
        success, result = FeatureService.update_feature(
            feature_id=feature_id,
            **data
        )
        
        if success:
            return APIResponse.success(
                data=result.to_dict(),
                message=SM.FEATURE_UPDATED
            )
        else:
            return APIResponse.error(
                message=EM.FEATURE_UPDATE_FAILED.format(reason=result),
                errors={'reason': result, 'feature_id': feature_id},
                status_code=400
            )
            
    except Exception as e:
        logger.exception(f"API error updating feature {feature_id}: {str(e)}")
        return APIResponse.error(
            message=EM.FEATURE_UPDATE_FAILED.format(reason=str(e)),
            errors={'error': str(e), 'feature_id': feature_id},
            status_code=500
        )


@feature_bp.route('/api/features/<int:feature_id>', methods=['DELETE'])
@login_required
@require_permission('features.delete')
def api_delete_feature(feature_id):
    """Delete feature - JSON API"""
    try:
        feature = FeatureService.get_feature(feature_id)
        if not feature:
            return APIResponse.error(
                message=EM.FEATURE_NOT_FOUND,
                errors={'feature_id': feature_id},
                status_code=404
            )
        
        success, message = FeatureService.delete_feature(feature_id)
        
        if success:
            return APIResponse.success(
                message=SM.FEATURE_DELETED
            )
        else:
            return APIResponse.error(
                message=EM.FEATURE_DELETE_FAILED.format(reason=message),
                errors={'reason': message, 'feature_id': feature_id},
                status_code=400
            )
            
    except Exception as e:
        logger.exception(f"API error deleting feature {feature_id}: {str(e)}")
        return APIResponse.error(
            message=EM.FEATURE_DELETE_FAILED.format(reason=str(e)),
            errors={'error': str(e), 'feature_id': feature_id},
            status_code=500
        )
```

### Step 3: Register Your Blueprint

```python
# app/blueprints/__init__.py or app/__init__.py

from app.blueprints.features.routes import feature_bp

def register_blueprints(app):
    # ... existing blueprints ...
    app.register_blueprint(feature_bp)
```

---

## Error Handling Patterns

### Pattern 1: Validation Errors (400)

```python
# Required field missing
if not name:
    return APIResponse.error(
        message=EM.FEATURE_VALIDATION_FAILED.format(field='name'),
        errors={'field': 'name', 'provided': name},
        status_code=400
    )

# Invalid format
if not isinstance(quantity, (int, float)) or quantity <= 0:
    return APIResponse.error(
        message=EM.INVENTORY_QUANTITY_INVALID,
        errors={'quantity': quantity, 'requirement': 'Must be positive number'},
        status_code=400
    )
```

### Pattern 2: Not Found Errors (404)

```python
item = InventoryItem.query.get(item_id)
if not item:
    # HTML route
    flash(EM.INVENTORY_NOT_FOUND, 'error')
    return redirect(url_for('inventory.list_inventory'))
    
    # API route
    return APIResponse.error(
        message=EM.INVENTORY_NOT_FOUND,
        errors={'inventory_id': item_id},
        status_code=404
    )
```

### Pattern 3: Permission Errors (403)

```python
if not has_permission('inventory.edit'):
    # HTML route
    flash(EM.PERMISSION_DENIED.format(permission='inventory.edit'), 'error')
    return redirect(url_for('app_routes.dashboard'))
    
    # API route
    return APIResponse.error(
        message=EM.PERMISSION_DENIED.format(permission='inventory.edit'),
        errors={'required_permission': 'inventory.edit'},
        status_code=403
    )
```

### Pattern 4: Business Logic Errors (400)

```python
if batch.status != 'in_progress':
    return APIResponse.error(
        message=EM.BATCH_INVALID_STATUS,
        errors={
            'batch_id': batch.id,
            'current_status': batch.status,
            'required_status': 'in_progress',
            'suggestion': 'Only batches in progress can be finished'
        },
        status_code=400
    )
```

### Pattern 5: Service Layer Failures

```python
try:
    success, result = SomeService.perform_operation(params)
    
    if success:
        flash(SM.OPERATION_SUCCESSFUL, 'success')
        return redirect(url_for('success.page'))
    else:
        # result contains error message/reason
        flash(EM.OPERATION_FAILED.format(reason=result), 'error')
        return redirect(url_for('retry.page'))
        
except Exception as e:
    logger.exception(f"Unexpected error in operation: {str(e)}")
    flash(EM.SYSTEM_ERROR, 'error')
    return redirect(url_for('safe.page'))
```

### Pattern 6: System Errors (500)

```python
try:
    # ... operation ...
except Exception as e:
    logger.exception(f"System error in feature_operation: {str(e)}")
    
    # HTML route
    flash(EM.SYSTEM_ERROR, 'error')
    return redirect(url_for('safe_fallback'))
    
    # API route
    return APIResponse.error(
        message=EM.SYSTEM_ERROR,
        errors={'error_id': str(uuid.uuid4())},  # For support tracking
        status_code=500
    )
```

---

## Scalability Considerations

### How This Scales

✅ **Message Addition** - Just add a new constant, no other changes needed  
✅ **Bulk Updates** - Change one message, updates everywhere it's used  
✅ **Team Growth** - New devs have clear patterns to follow  
✅ **Internationalization** - Easy to add translation layer later  
✅ **Error Tracking** - All errors go through same channels  

### When to Add New Messages

**DO add new messages when:**
- Creating a new feature/module
- Adding a new validation rule
- Implementing a new permission check
- Adding a new business logic constraint

**DON'T add redundant messages:**
- Reuse existing generic messages when appropriate
- Example: Use `EM.SYSTEM_ERROR` for unexpected errors, don't create `EM.FEATURE_SYSTEM_ERROR`

### Message Naming Convention

```
[ENTITY]_[ACTION]_[RESULT]
```

Examples:
- `INVENTORY_CREATE_FAILED` - Action failed
- `BATCH_NOT_FOUND` - Resource not found
- `RECIPE_UPDATED` - Action succeeded
- `TIMER_INVALID_STATUS` - Status check failed

---

## Testing Your Error Messages

### Unit Tests

```python
def test_create_feature_validation_error():
    """Test that validation errors return correct message"""
    from app.utils.error_messages import ErrorMessages as EM
    
    response = client.post('/api/features', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert EM.FEATURE_VALIDATION_FAILED.format(field='name') in data['message']


def test_feature_not_found_error():
    """Test that 404 returns correct message"""
    from app.utils.error_messages import ErrorMessages as EM
    
    response = client.get('/api/features/99999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['message'] == EM.FEATURE_NOT_FOUND
```

### Integration Tests

```python
def test_create_feature_success_message():
    """Test that success displays correct message"""
    from app.utils.error_messages import SuccessMessages as SM
    
    response = client.post(
        '/features/create',
        data={'name': 'Test Feature'},
        follow_redirects=True
    )
    assert SM.FEATURE_CREATED in response.get_data(as_text=True)
```

---

## Common Mistakes to Avoid

### ❌ DON'T: Create ad-hoc error strings

```python
# BAD
flash('Error creating the feature', 'error')
return jsonify({'error': 'Feature not found'}), 404
```

### ✅ DO: Use centralized messages

```python
# GOOD
from app.utils.error_messages import ErrorMessages as EM
flash(EM.FEATURE_CREATE_FAILED.format(reason='Details here'), 'error')
return APIResponse.error(message=EM.FEATURE_NOT_FOUND, status_code=404)
```

### ❌ DON'T: Forget flash categories

```python
# BAD - renders as blue info alert
flash('This is an error')
```

### ✅ DO: Always specify category

```python
# GOOD - renders as red error alert
flash(EM.SOME_ERROR, 'error')
```

### ❌ DON'T: Use f-strings in message definitions

```python
# BAD - Can't be reused with different values
FEATURE_ERROR = f"Failed to create {feature_name}"
```

### ✅ DO: Use format placeholders

```python
# GOOD - Reusable with any value
FEATURE_ERROR = "Failed to create {feature_name}"

# Usage
EM.FEATURE_ERROR.format(feature_name='Test')
```

### ❌ DON'T: Put HTML in error messages

```python
# BAD - Will render as literal text
FEATURE_ERROR = "Feature <strong>not found</strong>"
```

### ✅ DO: Use plain text (let templates handle formatting)

```python
# GOOD
FEATURE_ERROR = "Feature not found"
```

---

## Checklist for New Routes

When adding a new route, ensure:

- [ ] Error messages added to `error_messages.py`
- [ ] Success messages added to `error_messages.py`  
- [ ] Imported `ErrorMessages as EM`, `SuccessMessages as SM`
- [ ] Imported `APIResponse` for JSON routes
- [ ] All flash() calls include category ('error', 'success', etc.)
- [ ] API routes use APIResponse.error() / APIResponse.success()
- [ ] Logger configured at module level
- [ ] All exceptions logged with logger.exception()
- [ ] Validation errors return 400
- [ ] Not found errors return 404
- [ ] Permission errors return 403
- [ ] System errors return 500
- [ ] Tests added for error cases
- [ ] Tests verify correct error messages

---

## Migration Guide

To migrate existing routes to this pattern:

1. **Identify all error messages** in the route file
2. **Add them to `error_messages.py`** in the appropriate section
3. **Import EM/SM** at the top of your route file
4. **Replace all flash() calls** to use EM/SM with categories
5. **Replace all jsonify() errors** with APIResponse
6. **Test thoroughly** to ensure messages still display correctly

Example migration:

```python
# BEFORE
flash('Inventory item not found', 'error')
return jsonify({'error': 'Failed to update'}), 400

# AFTER
from app.utils.error_messages import ErrorMessages as EM
from app.utils.api_responses import APIResponse

flash(EM.INVENTORY_NOT_FOUND, 'error')
return APIResponse.error(
    message=EM.INVENTORY_UPDATE_FAILED.format(reason='Reason here'),
    errors={'inventory_id': item_id},
    status_code=400
)
```

---

## Future Improvements

### Planned Features

1. **Internationalization (i18n)** - Add translation support
2. **Error Tracking Integration** - Link errors to Sentry/logging
3. **User Feedback Loop** - Allow users to report confusing messages
4. **Error Analytics** - Track which errors occur most frequently

### How to Extend

The system is designed to grow:

- **Add new message classes** - Create `DebugMessages`, `NotificationMessages`, etc.
- **Add severity levels** - Tag messages with `critical`, `high`, `medium`, `low`
- **Add help links** - Include documentation URLs for common errors
- **Add error codes** - Add unique codes for support tracking

Example extension:

```python
class ErrorMessages:
    # Enhanced with error codes and help links
    INVENTORY_NOT_FOUND = {
        'message': "Inventory item not found.",
        'code': 'ERR_INV_001',
        'help_url': '/docs/inventory/troubleshooting#not-found'
    }
```

---

## Questions?

For questions about this protocol:
1. Check existing routes for examples
2. Review `app/utils/error_messages.py` for similar messages
3. Ask the team lead or submit a PR for discussion
4. Document new patterns here for future developers

**Remember**: Consistency is key. When in doubt, follow existing patterns.
