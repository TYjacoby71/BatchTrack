# Users & Permissions System

BatchTrack uses a **clear, hierarchical user and permission system** designed for multi-tenant SaaS. This guide explains how users, roles, and subscription tiers interact.

---

## 1. User Types (Immutable)

User types are **hard-coded classifications**. They are NOT roles and should never be stored in the same table as roles.

| User Type | Scope | Organization ID | Permissions | Purpose |
|-----------|-------|------------------|------------|---------|
| **Developer** | System-wide | **None** | All permissions globally | BatchTrack staff/admin only |
| **Organization Owner** | Single organization | Required | All permissions available to their subscription tier | Business owner |
| **Team Member** | Single organization | Required | Based on assigned roles | Staff invited by org owner |

✅ **Rules:**
- Developers exist **outside the SaaS customer side**.  
- Org Owners & Team Members always belong to an organization (`organization_id` required).  
- Developers should never receive `organization_id`.  

---

## 2. Roles

Roles are **permission groupings** and are the bridge between users and permissions.

| Role Type | Created By | Editable By | Notes |
|-----------|------------|-------------|-------|
| **System Roles** | Developers | No | Predefined defaults (e.g., "Production Manager") |
| **Custom Roles** | Organization Owners | Yes | Scoped to their organization |

### Default System Roles

| Role | Permissions |
|------|-------------|
| **Production Manager** | `batch.start`, `batch.finish`, `inventory.adjust` |
| **Inventory Specialist** | `inventory.restock`, `inventory.adjust`, `reports.view` |
| **Viewer** | `reports.view` only |

✅ **Organization owners automatically have ALL permissions available for their subscription tier.**

---

## 3. Permissions

Permissions are **atomic actions** (never tied directly to user types).  
Example categories:

| Category | Example Permissions |
|----------|---------------------|
| **batches** | `batch.start`, `batch.finish`, `batch.cancel` |
| **inventory** | `inventory.adjust`, `inventory.restock`, `inventory.view` |
| **products** | `product.create`, `product.archive` |
| **users** | `user.invite`, `user.assign_roles` |
| **reports** | `reports.view`, `reports.export` |
| **settings** | `settings.update`, `settings.manage_roles` |

✅ **Never hardcode permissions** in routes — always check via:

```python
if has_permission(current_user, 'inventory.adjust'):
    # allowed action
```

---

## 4. Subscription Tiers

Subscription tiers determine which permissions can even be granted to users in that organization.

| Tier | Max Users | Features / Permission Categories |
|------|-----------|----------------------------------|
| **Free** | 1 active user | Basic production tracking, limited inventory |
| **Team** | 10 active users | Full batch & inventory features, custom roles |
| **Enterprise** | Unlimited | All features, API integration |

✅ **Inactive users do NOT count toward subscription limits.**

---

## 5. User Management Workflow

### Developer Workflow
1. Developer logs into developer dashboard (separate from SaaS UI).
2. Can view or impersonate organizations for support.
3. No `organization_id` is ever assigned.

### Organization Owner Workflow
1. Access Organization Dashboard.
2. Create Custom Roles with available permissions.
3. Invite team members (via email).
4. Assign roles to team members.

### Team Member Workflow
1. Accepts invitation and creates account.
2. Only sees features they have permissions for.

---

## 6. Data Scoping Rules

### Scoped Models
All models except Developers are scoped by `organization_id`.

```python
class ScopedModelMixin:
    organization_id = db.Column(
        db.Integer, db.ForeignKey('organization.id'), nullable=False
    )

    @classmethod
    def for_organization(cls, org_id):
        return cls.query.filter_by(organization_id=org_id)
```

### Developer Pattern
Developers select an organization to view customer data but never modify their own user type.

```python
if current_user.user_type == "developer":
    data = Model.for_organization(selected_org_id)
else:
    data = Model.for_organization(current_user.organization_id)
```

---

## 7. Permission Checking

### Route Example
```python
@require_permission('inventory.adjust')
def adjust_inventory_route():
    # Authorized only if user has permission
```

### Template Example
```html
{% if has_permission('user.invite') %}
<button class="btn btn-primary">Invite User</button>
{% endif %}
```

---

## 8. Best Practices

✔ Developers NEVER receive roles or organization IDs.  
✔ Always filter by `organization_id` for customer data.  
✔ Org Owners always have all tier-allowed permissions (don't reassign manually).  
✔ Only Team Members are role-limited.  
✔ All permissions must be stored in DB, no hardcoding.