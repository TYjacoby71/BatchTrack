# Route Development Guide

## Quick Start Template

Copy this template when creating a new route file:

```python
"""
Module: [Feature Name] Routes
Description: [Brief description of what this module handles]
"""

from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template
from flask_login import login_required, current_user
from app.utils.permissions import require_permission
from app.utils.error_messages import ErrorMessages as EM, SuccessMessages as SM
from app.utils.api_responses import APIResponse
from app.models import db, [YourModel]
from app.services.[your_service] import [YourService]
import logging

logger = logging.getLogger(__name__)

# Create blueprint
[feature]_bp = Blueprint('[feature]', __name__, url_prefix='/[feature]')


# ============================================================================
# HTML ROUTES (User-facing pages)
# ============================================================================

@[feature]_bp.route('/')
@login_required
@require_permission('[feature].view')
def list_[feature]():
    """List view - returns HTML"""
    try:
        items = [YourService].get_all(
            organization_id=current_user.organization_id
        )
        return render_template('[feature]/list.html', items=items)
    except Exception as e:
        logger.exception(f"Error listing [feature]: {str(e)}")
        flash(EM.SYSTEM_ERROR, 'error')
        return redirect(url_for('app_routes.dashboard'))


@[feature]_bp.route('/<int:item_id>')
@login_required
@require_permission('[feature].view')
def view_[feature](item_id):
    """Detail view - returns HTML"""
    try:
        item = [YourService].get_by_id(item_id)
        if not item:
            flash(EM.[FEATURE]_NOT_FOUND, 'error')
            return redirect(url_for('[feature].list_[feature]'))
        
        return render_template('[feature]/view.html', item=item)
    except Exception as e:
        logger.exception(f"Error viewing [feature] {item_id}: {str(e)}")
        flash(EM.SYSTEM_ERROR, 'error')
        return redirect(url_for('[feature].list_[feature]'))


# ============================================================================
# API ROUTES (JSON endpoints)
# ============================================================================

@[feature]_bp.route('/api/[feature]', methods=['GET'])
@login_required
@require_permission('[feature].view')
def api_list_[feature]():
    """List API - returns JSON"""
    try:
        items = [YourService].get_all(
            organization_id=current_user.organization_id
        )
        return APIResponse.success(
            data=[item.to_dict() for item in items],
            message="Items retrieved successfully"
        )
    except Exception as e:
        logger.exception(f"API error listing [feature]: {str(e)}")
        return APIResponse.error(message=EM.SYSTEM_ERROR, status_code=500)


@[feature]_bp.route('/api/[feature]/<int:item_id>', methods=['GET'])
@login_required
@require_permission('[feature].view')
def api_get_[feature](item_id):
    """Get single item API - returns JSON"""
    try:
        item = [YourService].get_by_id(item_id)
        if not item:
            return APIResponse.error(
                message=EM.[FEATURE]_NOT_FOUND,
                errors={'item_id': item_id},
                status_code=404
            )
        
        return APIResponse.success(data=item.to_dict())
    except Exception as e:
        logger.exception(f"API error getting [feature] {item_id}: {str(e)}")
        return APIResponse.error(
            message=EM.SYSTEM_ERROR,
            errors={'item_id': item_id},
            status_code=500
        )


@[feature]_bp.route('/api/[feature]', methods=['POST'])
@login_required
@require_permission('[feature].create')
def api_create_[feature]():
    """Create API - returns JSON"""
    try:
        data = request.get_json()
        if not data:
            return APIResponse.error(
                message=EM.VALIDATION_JSON_REQUIRED,
                status_code=400
            )
        
        # Validation
        required_fields = ['name', 'other_field']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return APIResponse.error(
                message=EM.VALIDATION_REQUIRED_FIELDS.format(
                    fields=', '.join(missing)
                ),
                errors={'missing_fields': missing},
                status_code=400
            )
        
        # Service call
        success, result = [YourService].create(
            data=data,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        
        if success:
            return APIResponse.success(
                data=result.to_dict(),
                message=SM.[FEATURE]_CREATED,
                status_code=201
            )
        else:
            return APIResponse.error(
                message=EM.[FEATURE]_CREATE_FAILED.format(reason=result),
                errors={'reason': result},
                status_code=400
            )
            
    except Exception as e:
        logger.exception(f"API error creating [feature]: {str(e)}")
        return APIResponse.error(
            message=EM.[FEATURE]_CREATE_FAILED.format(reason=str(e)),
            status_code=500
        )
```

---

## File Organization

```
app/
├── blueprints/
│   └── [feature]/
│       ├── __init__.py          # Blueprint registration
│       ├── routes.py            # Route handlers (this file)
│       └── templates/           # HTML templates
│           ├── list.html
│           └── view.html
├── services/
│   └── [feature]_service.py    # Business logic
├── models/
│   └── [feature].py            # Database models
└── utils/
    ├── error_messages.py        # Centralized messages
    └── api_responses.py         # Response utilities
```

---

## Response Patterns

### HTML Route Success
```python
flash(SM.OPERATION_SUCCESSFUL, 'success')
return redirect(url_for('[feature].view_item', item_id=item.id))
```

### HTML Route Error
```python
flash(EM.OPERATION_FAILED.format(reason='Details'), 'error')
return redirect(url_for('[feature].list_items'))
```

### API Success (200)
```python
return APIResponse.success(
    data=item.to_dict(),
    message=SM.OPERATION_SUCCESSFUL
)
```

### API Created (201)
```python
return APIResponse.success(
    data=new_item.to_dict(),
    message=SM.ITEM_CREATED,
    status_code=201
)
```

### API Validation Error (400)
```python
return APIResponse.error(
    message=EM.VALIDATION_FAILED,
    errors={'field': 'name', 'issue': 'required'},
    status_code=400
)
```

### API Not Found (404)
```python
return APIResponse.error(
    message=EM.ITEM_NOT_FOUND,
    errors={'item_id': item_id},
    status_code=404
)
```

### API Permission Error (403)
```python
return APIResponse.error(
    message=EM.PERMISSION_DENIED.format(permission='required_permission'),
    status_code=403
)
```

### API System Error (500)
```python
logger.exception(f"System error: {str(e)}")
return APIResponse.error(
    message=EM.SYSTEM_ERROR,
    status_code=500
)
```

---

## Validation Patterns

### Required Fields
```python
required = ['name', 'quantity', 'unit']
missing = [f for f in required if not data.get(f)]
if missing:
    return APIResponse.error(
        message=EM.VALIDATION_REQUIRED_FIELDS.format(fields=', '.join(missing)),
        errors={'missing_fields': missing},
        status_code=400
    )
```

### Type Validation
```python
try:
    quantity = float(data.get('quantity'))
    if quantity <= 0:
        raise ValueError("Must be positive")
except (TypeError, ValueError) as e:
    return APIResponse.error(
        message=EM.VALIDATION_INVALID_FORMAT.format(field='quantity'),
        errors={'field': 'quantity', 'provided': data.get('quantity')},
        status_code=400
    )
```

### Permission Check
```python
from app.utils.permissions import has_permission

if not has_permission('[feature].edit'):
    # HTML
    flash(EM.PERMISSION_DENIED.format(permission='[feature].edit'), 'error')
    return redirect(url_for('app_routes.dashboard'))
    
    # API
    return APIResponse.error(
        message=EM.PERMISSION_DENIED.format(permission='[feature].edit'),
        status_code=403
    )
```

---

## Logging Best Practices

```python
import logging

logger = logging.getLogger(__name__)

# INFO - Normal operations
logger.info(f"Creating [feature] for user {current_user.id}")

# WARNING - Unexpected but handled
logger.warning(f"Duplicate [feature] name detected: {name}")

# ERROR - Operation failed but recoverable
logger.error(f"Failed to create [feature]: {error_msg}")

# EXCEPTION - Unhandled errors (includes stack trace)
logger.exception(f"Unexpected error in [feature] creation: {str(e)}")
```

**When to log:**
- ✅ All exceptions in try/except blocks
- ✅ Permission denials
- ✅ Validation failures (if unusual)
- ✅ Service layer failures
- ❌ Don't log successful operations (clutters logs)
- ❌ Don't log expected validation errors

---

## Testing Your Routes

### Test File Structure
```python
# tests/test_[feature]_routes.py

import pytest
from app.utils.error_messages import ErrorMessages as EM, SuccessMessages as SM

class TestFeatureRoutes:
    """Test [Feature] routes"""
    
    def test_list_requires_auth(self, client):
        """Test that list route requires authentication"""
        response = client.get('/[feature]/')
        assert response.status_code == 302  # Redirect to login
    
    def test_create_success(self, client, auth_user):
        """Test successful creation"""
        response = client.post(
            '/api/[feature]',
            json={'name': 'Test', 'quantity': 10},
            headers={'Authorization': f'Bearer {auth_user.token}'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['message'] == SM.FEATURE_CREATED
    
    def test_create_validation_error(self, client, auth_user):
        """Test validation error handling"""
        response = client.post(
            '/api/[feature]',
            json={},  # Missing required fields
            headers={'Authorization': f'Bearer {auth_user.token}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'missing_fields' in data['errors']
    
    def test_not_found_error(self, client, auth_user):
        """Test 404 error handling"""
        response = client.get(
            '/api/[feature]/99999',
            headers={'Authorization': f'Bearer {auth_user.token}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data['message'] == EM.FEATURE_NOT_FOUND
```

---

## Performance Considerations

### Pagination
```python
@[feature]_bp.route('/api/[feature]', methods=['GET'])
def api_list_[feature]():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = [YourModel].query.filter_by(
        organization_id=current_user.organization_id
    )
    
    pagination = query.paginate(
        page=page,
        per_page=min(per_page, 100),  # Cap at 100
        error_out=False
    )
    
    return APIResponse.success(
        data={
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        }
    )
```

### Eager Loading
```python
# BAD - N+1 queries
items = [YourModel].query.all()
for item in items:
    print(item.related_object.name)  # Triggers query per item

# GOOD - Single query
from sqlalchemy.orm import joinedload

items = [YourModel].query.options(
    joinedload([YourModel].related_object)
).all()
```

---

## Security Checklist

When creating routes, ensure:

- [ ] Authentication required (`@login_required`)
- [ ] Permissions checked (`@require_permission()`)
- [ ] Organization scoping enforced
- [ ] CSRF protection enabled (automatic for form posts)
- [ ] Input validation performed
- [ ] SQL injection prevented (use ORM, not raw SQL)
- [ ] No sensitive data in error messages
- [ ] No stack traces exposed to users
- [ ] Rate limiting considered for public APIs
- [ ] File uploads validated (if applicable)

---

## Common Pitfalls

### ❌ Missing Organization Scoping
```python
# BAD - Shows items from all organizations
items = [YourModel].query.all()
```

```python
# GOOD - Only shows user's organization
items = [YourModel].query.filter_by(
    organization_id=current_user.organization_id
).all()
```

### ❌ Not Handling None Results
```python
# BAD - Will throw exception if not found
item = [YourModel].query.get(item_id)
return render_template('view.html', item=item)
```

```python
# GOOD - Handles not found case
item = [YourModel].query.get(item_id)
if not item:
    flash(EM.ITEM_NOT_FOUND, 'error')
    return redirect(url_for('[feature].list_items'))
return render_template('view.html', item=item)
```

### ❌ Mixing HTML and API Logic
```python
# BAD - Single route handles both
@[feature]_bp.route('/create', methods=['POST'])
def create_[feature]():
    if request.is_json:
        # API logic
    else:
        # HTML logic
```

```python
# GOOD - Separate routes
@[feature]_bp.route('/create', methods=['POST'])
def create_[feature]():
    # HTML logic only
    
@[feature]_bp.route('/api/[feature]', methods=['POST'])
def api_create_[feature]():
    # API logic only
```

---

## Quick Reference Commands

```bash
# Run tests for your feature
pytest tests/test_[feature]_routes.py -v

# Check for linter errors
flake8 app/blueprints/[feature]/routes.py

# Run just your blueprint
flask run --debug

# Test single route
curl -X GET http://localhost:5000/api/[feature] \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Need Help?

1. Check existing routes in similar features
2. Review `ERROR_MESSAGE_PROTOCOL.md` for error handling
3. See `app/utils/error_messages.py` for available messages
4. Ask team lead or submit draft PR for feedback
