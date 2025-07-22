
# Users & Permissions System

BatchTrack uses a **role-based permission system** designed for multi-tenant SaaS. This guide explains the current implementation.

---

## 1. User Types (Immutable)

User types are **hard-coded classifications** that determine system access scope.

| User Type | Scope | Organization ID | Purpose |
|-----------|-------|------------------|---------|
| **Developer** | System-wide | **None** | BatchTrack staff/admin - exists outside SaaS |
| **Organization Owner** | Single organization | Required | Business owner with full tier permissions |
| **Team Member** | Single organization | Required | Staff invited by org owner |

✅ **Rules:**
- Developers exist **outside the SaaS customer side** with no `organization_id`
- Org Owners & Team Members always belong to an organization (`organization_id` required)
- User type determines initial access scope, roles determine specific permissions

---

## 2. Current Role System

### System Roles (Currently Implemented)

| Role | Type | Description | Assigned To |
|------|------|-------------|-------------|
| **organization_owner** | System Role | Full access to all permissions within subscription tier | Organization owners automatically |
| **team_member** | System Role | Basic role for invited users | Team members by default |
| **system_admin** | Developer Role | System-wide admin access | Developer users only |

### Role Assignment Rules

- **Organization Owners**: Automatically receive `organization_owner` role with ALL permissions available in their subscription tier
- **Team Members**: Receive `team_member` role by default (permissions can be customized via custom roles)
- **Developers**: Receive `system_admin` developer role for system management

---

## 3. Permission Categories

Permissions are **atomic actions** organized by functional area:

| Category | Example Permissions |
|----------|---------------------|
| **batches** | `batch.start`, `batch.finish`, `batch.cancel`, `batch.view` |
| **inventory** | `inventory.adjust`, `inventory.view`, `inventory.restock` |
| **products** | `product.create`, `product.view`, `product.edit`, `product.archive` |
| **recipes** | `recipe.create`, `recipe.view`, `recipe.edit` |
| **organization** | `organization.manage`, `user.invite`, `user.manage` |
| **system** | `system.admin` (developers only) |

✅ **Always check permissions via:**

```python
if has_permission('inventory.adjust'):
    # allowed action
```

**Never hardcode user types in route logic.**

---

## 4. Subscription Tiers & Permissions

Subscription tiers determine which permissions are **available** to be granted within an organization.

| Tier | Max Users | Available Permission Categories |
|------|-----------|--------------------------------|
| **Solo** | 1 active user | All core features (batch, inventory, recipes, products) |
| **Team** | 10 active users | All features + user management, custom roles |
| **Enterprise** | Unlimited | All features + advanced reporting, API access |

✅ **Permission Enforcement:**
- Organization owners get ALL permissions allowed by their tier
- Custom roles can only grant permissions within the tier limits
- Inactive users don't count toward limits

---

## 5. Custom Roles (Future Enhancement)

*Currently, the system supports custom roles but the UI is primarily focused on system roles.*

Organization owners can create custom roles by:
1. Selecting permissions from their tier's available set
2. Assigning the role to team members
3. Managing role assignments through the Organization Dashboard

---

## 6. Data Scoping

### Multi-tenant Filtering
All customer data is scoped by `organization_id`:

```python
# Correct - scoped query
inventory = Inventory.query.filter_by(organization_id=current_user.organization_id).all()

# Developer pattern - can view any organization
if current_user.user_type == "developer":
    inventory = Inventory.query.filter_by(organization_id=selected_org_id).all()
```

### Developer Access Pattern
Developers can select an organization to view customer data but never modify their own user type:

```python
if current_user.user_type == "developer":
    # Developer viewing customer data
    data = Model.for_organization(selected_org_id)
else:
    # Normal customer access
    data = Model.for_organization(current_user.organization_id)
```

---

## 7. Permission Checking in Code

### Route Protection
```python
from app.utils.permissions import require_permission

@require_permission('inventory.adjust')
def adjust_inventory_route():
    # Only accessible if user has permission
    pass
```

### Template Conditionals
```html
{% if has_permission('user.invite') %}
<button class="btn btn-primary">Invite User</button>
{% endif %}
```

### Function Checks
```python
from app.utils.permissions import has_permission

if has_permission('batch.start'):
    # User can start batches
    pass
```

---

## 8. Current System Architecture

### Models
- `User` - Contains user_type field
- `Role` - System and custom roles
- `Permission` - Atomic permission definitions  
- `UserRoleAssignment` - Links users to roles
- `DeveloperRole`/`DeveloperPermission` - Separate developer system

### Key Services
- `PermissionService` - Permission checking logic
- `UserService` - User management and role assignment
- `SubscriptionService` - Tier-based permission filtering

---

## 9. Development Best Practices

✔ **Always use `has_permission()` - never check user_type directly**  
✔ **Filter by `organization_id` for all customer data**  
✔ **Developers get system-wide access but no organization association**  
✔ **Organization owners automatically have all tier permissions**  
✔ **Store all permissions in database - no hardcoding**  
✔ **Use permission categories for logical grouping**  

❌ **Never bypass the permission system**  
❌ **Don't hardcode role names in business logic**  
❌ **Don't assign organization_id to developers**

---

## 10. Migration Notes

This system evolved from a hardcoded user-type system to flexible role-based permissions. The current implementation maintains backward compatibility while providing the foundation for advanced permission management.

**Key Changes Made:**
- Removed hardcoded permission checks based on user_type
- Implemented role-based permission checking
- Added subscription tier permission filtering
- Separated developer permissions from customer permissions
- Maintained data scoping by organization_id
