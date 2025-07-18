
# Development Guide

**How to safely extend BatchTrack while maintaining system integrity**

## Core Development Principles

### 1. Service Authority (NEVER BYPASS)
- **FIFO Service**: All inventory deductions must go through `FIFOService`
- **Inventory Adjustment Service**: All stock changes via `InventoryAdjustmentService`
- **Unit Conversion Service**: All conversions through `UnitConversionService`
- **Stock Check Service**: All availability checks via `StockCheckService`

### 2. Organization Scoping (ALWAYS ENFORCE)
- Every scoped model must filter by `organization_id`
- Developers use `session['dev_selected_org_id']` when in customer support mode
- Never expose cross-organization data

### 3. Permission Checking (NO HARDCODING)
- Use `has_permission(permission_name)` for all access control
- Check subscription tier limits before feature access
- Implement template-level permission hiding

## Adding New Features

### 1. Planning Phase
```markdown
## Feature: [Feature Name]
- **Service Authority**: Which service owns this feature?
- **Data Scoping**: What organization_id filtering is needed?
- **Permissions**: What new permissions are required?
- **Subscription Tiers**: Which tiers can access this?
- **Database Changes**: New models or fields needed?
```

### 2. Database Changes
```python
# Always include organization scoping
class NewModel(ScopedModelMixin, db.Model):
    __tablename__ = 'new_model'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, 
                               db.ForeignKey('organization.id'), 
                               nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
```

### 3. Service Integration
```python
# Create or extend appropriate service
class NewFeatureService:
    @staticmethod
    def process_action(organization_id, data):
        # Always validate organization access
        if not current_user.can_access_organization(organization_id):
            raise PermissionError("Access denied")
        
        # Use existing services for related operations
        if needs_inventory_change:
            return InventoryAdjustmentService.adjust_stock(...)
```

### 4. Route Implementation
```python
@blueprint.route('/new-feature', methods=['POST'])
@login_required
@require_permission('new_feature_permission')
def new_feature():
    # Always validate and scope data
    org_id = get_current_organization_id()
    
    # Use service for business logic
    result = NewFeatureService.process_action(org_id, request.json)
    
    return jsonify(result)
```

## Code Organization

### Directory Structure
```
app/
├── blueprints/           # Route handlers by feature
│   ├── feature_name/
│   │   ├── __init__.py
│   │   ├── routes.py     # HTTP endpoints
│   │   └── services.py   # Business logic
├── models/               # Database models
├── services/             # Core business services
├── utils/                # Helper functions
└── templates/            # Frontend templates
    └── feature_name/     # Feature-specific templates
```

### Service Layer Architecture
```python
# Core services (DO NOT MODIFY without team approval)
- FIFOService
- InventoryAdjustmentService  
- UnitConversionService
- StockCheckService

# Feature services (Safe to extend)
- ProductService
- BatchService
- ReportService
- AlertService
```

## API Development

### Endpoint Patterns
```python
# Organization-scoped endpoints
@api.route('/api/feature/<int:item_id>')
def get_item(item_id):
    org_id = get_current_organization_id()
    item = Item.query.filter_by(
        id=item_id, 
        organization_id=org_id
    ).first_or_404()
    return jsonify(item.to_dict())

# Developer support endpoints
@api.route('/api/admin/organizations/<int:org_id>/feature')
@require_developer_access
def admin_feature(org_id):
    # Developer can access any organization
    items = Item.query.filter_by(organization_id=org_id).all()
    return jsonify([item.to_dict() for item in items])
```

### Response Formats
```python
# Success responses
{
    "success": true,
    "data": { ... },
    "message": "Optional success message"
}

# Error responses
{
    "success": false,
    "error": "Error description",
    "details": { ... }  # Optional additional context
}
```

## Frontend Development

### JavaScript Patterns
```javascript
// Organization-aware API calls
async function apiCall(endpoint, data = {}) {
    const response = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(data)
    });
    
    if (!response.ok) {
        throw new Error(`API call failed: ${response.statusText}`);
    }
    
    return response.json();
}

// Permission-aware UI updates
function updateUI() {
    if (hasPermission('manage_inventory')) {
        document.getElementById('edit-button').style.display = 'block';
    }
}
```

### Template Patterns
```html
<!-- Permission-based feature hiding -->
{% if has_permission('manage_users') %}
    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#inviteModal">
        Invite User
    </button>
{% endif %}

<!-- Subscription tier features -->
{% if has_subscription_feature('advanced_alerts') %}
    <div class="advanced-alerts-section">
        <!-- Enterprise features here -->
    </div>
{% endif %}
```

## Testing Guidelines

### Unit Tests
```python
def test_service_respects_organization_scoping():
    # Create test organizations
    org1 = create_test_organization()
    org2 = create_test_organization()
    
    # Create data in each org
    item1 = create_test_item(organization_id=org1.id)
    item2 = create_test_item(organization_id=org2.id)
    
    # Service should only return org1's data
    result = ServiceClass.get_items(org1.id)
    assert item1.id in [r.id for r in result]
    assert item2.id not in [r.id for r in result]
```

### Integration Tests
```python
def test_permission_enforcement():
    user = create_test_user(permissions=['view_batches'])
    
    with app.test_client() as client:
        login_user(client, user)
        
        # Should succeed - user has permission
        response = client.get('/batches')
        assert response.status_code == 200
        
        # Should fail - user lacks permission
        response = client.post('/batches/new')
        assert response.status_code == 403
```

## Common Pitfalls

### ❌ DON'T: Bypass Services
```python
# WRONG: Direct database manipulation
inventory_item.quantity -= used_quantity
db.session.commit()
```

### ✅ DO: Use Services
```python
# CORRECT: Use FIFO service
FIFOService.deduct_inventory(
    ingredient_id=ingredient.id,
    quantity=used_quantity,
    organization_id=org_id
)
```

### ❌ DON'T: Ignore Organization Scoping
```python
# WRONG: Cross-organization data leak
items = Item.query.all()
```

### ✅ DO: Always Scope by Organization
```python
# CORRECT: Organization-scoped queries
items = Item.query.filter_by(organization_id=org_id).all()
```

### ❌ DON'T: Hardcode Permissions
```python
# WRONG: Hardcoded role check
if current_user.role == 'admin':
    return render_template('admin_panel.html')
```

### ✅ DO: Use Permission System
```python
# CORRECT: Permission-based access
if has_permission('admin_access'):
    return render_template('admin_panel.html')
```

## Code Review Checklist

### Before Submitting
- [ ] All database queries scoped by `organization_id`
- [ ] New permissions added to permission seeder
- [ ] Services used for all business logic
- [ ] Frontend respects permission system
- [ ] Tests cover organization isolation
- [ ] Documentation updated if needed

### During Review
- [ ] No service bypassing
- [ ] Proper error handling
- [ ] Security considerations addressed
- [ ] Performance implications considered
- [ ] Code follows established patterns

## Emergency Procedures

### Production Issues
1. **Identify Impact**: Which organizations/users affected?
2. **Immediate Response**: Can issue be resolved with existing admin tools?
3. **Hotfix Process**: Minimal change to resolve critical issues
4. **Post-Incident**: Update documentation and add preventive measures

### Data Recovery
1. **Backup Access**: Daily backups available in `/backups/`
2. **Point-in-Time Recovery**: Database supports transaction log recovery
3. **Organization Isolation**: Issues typically isolated to single organization
4. **Audit Trail**: All changes logged for investigation

## Getting Help

### Documentation First
1. Check `/docs` folder for existing guidance
2. Review related service documentation
3. Look for similar implementations in codebase

### Code Review
1. Tag senior developers for complex changes
2. Include detailed description of changes
3. Explain business logic and edge cases
4. Highlight any service integrations

### Best Practices
- Start with small, isolated changes
- Test thoroughly in development environment
- Follow established patterns and conventions
- Document any new patterns or approaches
