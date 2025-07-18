
# User & Permission System

**Complete guide to BatchTrack's multi-tenant user management**

## User Types

### Developer
- **Scope**: System-wide access
- **Organization**: Not assigned to any organization
- **Permissions**: All permissions globally
- **Purpose**: System administration and customer support

### Organization Owner
- **Scope**: Single organization
- **Organization**: Owns one organization
- **Permissions**: All permissions available to their subscription tier
- **Purpose**: Business owner, manages team and settings

### Team Member
- **Scope**: Single organization
- **Organization**: Assigned to organization
- **Permissions**: Based on assigned roles
- **Purpose**: Production staff, managers, specialists

## Permission System

### Permission Categories
- **alerts**: Alert management and configuration
- **batches**: Production batch management
- **inventory**: Stock management and adjustments
- **products**: Product and recipe management
- **reports**: Analytics and reporting
- **settings**: Organization configuration
- **users**: User and role management

### Subscription Tier Permissions
```
Free Tier:
- Basic production tracking
- Limited inventory management
- 1 user maximum

Team Tier:
- Full production features
- Advanced inventory management
- User management
- Custom roles
- 10 users maximum

Enterprise Tier:
- All features
- API access
- Priority support
- Unlimited users
```

## Role Management

### System Roles (Cannot be deleted)
- **Production Manager**: Full batch and inventory access
- **Inventory Specialist**: Stock management focus
- **Viewer**: Read-only access to most features

### Custom Roles
- Organization owners can create custom roles
- Assign specific permissions from available categories
- Must respect subscription tier limitations

## User Management Workflow

### Developer Support Mode
1. Developer selects organization from dashboard
2. Gains organization owner permissions for that org
3. Can manage users, roles, and settings
4. Actions logged for audit trail

### Organization Owner Workflow
1. Access organization dashboard
2. Create custom roles with specific permissions
3. Invite users via email
4. Assign roles to team members
5. Monitor user activity and permissions

### Team Member Experience
1. Receives invitation email
2. Sets up account with temporary password
3. Permissions determined by assigned roles
4. Can only access features allowed by subscription tier

## Permission Checking

### Code Implementation
```python
# Check specific permission
if has_permission('manage_inventory'):
    # Allow inventory management

# Check role
if has_role('Production Manager'):
    # Allow production management

# Check subscription feature
if has_subscription_feature('advanced_alerts'):
    # Show advanced alert options
```

### Permission Inheritance
- Developers: All permissions
- Organization Owners: All permissions for their tier
- Team Members: Only assigned role permissions
- All permissions respect subscription tier limits

## Data Scoping Rules

### Organization Isolation
- All data filtered by `organization_id`
- Users can only see their organization's data
- Developers can switch between organizations

### Developer Access
- Can view any organization's data
- Must select organization to access customer features
- Actions logged for security and support

## Security Considerations

### Authentication
- Flask-Login session management
- Password hashing with Werkzeug
- CSRF protection on all forms

### Authorization
- Permission checks on every protected route
- Service-level permission validation
- Template-level feature hiding

### Audit Trail
- User creation and role assignments logged
- Permission changes tracked
- Developer access actions recorded

## Common Permission Patterns

### Feature Gating
```python
@require_permission('manage_batches')
def create_batch():
    # Only users with batch management permission
```

### Template Conditionals
```html
{% if has_permission('manage_users') %}
    <button>Invite User</button>
{% endif %}
```

### Subscription Checks
```python
if user.organization.subscription_tier == 'enterprise':
    # Enterprise-only features
```

## Troubleshooting

### User Can't Access Feature
1. Check user's assigned roles
2. Verify role has required permission
3. Confirm permission available for subscription tier
4. Check if user is active

### Permission Not Working
1. Verify permission exists in database
2. Check permission category assignment
3. Confirm subscription tier requirements
4. Validate role-permission associations

### Organization Limits
1. Check active user count vs subscription limit
2. Verify user type exclusions (developers don't count)
3. Review subscription tier capabilities
