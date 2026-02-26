# Users & Permissions System

## Synopsis
Users inherit permissions through roles and subscription tiers, with add-ons providing optional entitlements and feature toggles.

BatchTrack uses a **clear, hierarchical user and permission system** designed for multi-tenant SaaS. This guide explains how users, roles, and subscription tiers interact.

---

## Glossary
- **Permission**: Atomic action allowed in the system.
- **Role**: Permission bundle assigned to a user.

---

## 1. User Types (Immutable)

User types are **hard-coded classifications** stored in `user_type`. They are NOT roles and should never be stored in the same table as roles.

| `user_type` value | Scope | Organization ID | Permissions | Purpose |
|-------------------|-------|------------------|------------|---------|
| **`developer`** | System-wide | **None** | All permissions globally | BatchTrack staff/admin only |
| **`customer`** (owner) | Single organization | Required | All permissions available to their subscription tier | Business owner (`is_organization_owner=True`) |
| **`customer`** (team member) | Single organization | Required | Based on assigned roles | Staff invited by org owner |

✅ **Rules:**
- Only two `user_type` values exist: `developer` and `customer`.
- Organization owners are customers with `is_organization_owner=True` and the `organization_owner` role.
- Developers exist **outside the SaaS customer side**.  
- Customers always belong to an organization (`organization_id` required).  
- Developers should never receive `organization_id`.  

---

## 2. Roles

Roles are **permission groupings** and are the bridge between users and permissions.

| Role Type | Created By | Editable By | Notes |
|-----------|------------|-------------|-------|
| **System Roles** | Platform seed | No | `organization_owner` (org-level), plus developer roles |
| **Custom Roles** | Organization Owners | Yes | Scoped to their organization |

### System Roles

| Role | Scope | Permissions |
|------|-------|-------------|
| **`organization_owner`** | Organization | All permissions allowed by the org's subscription tier |
| **`system_admin`** | Developer | Full system administration across all organizations |
| **`developer`** | Developer | Basic developer access for debugging |
| **`support`** | Developer | Read-only access for customer support |

✅ **Organization owners automatically have ALL permissions available for their subscription tier.**

---

## 3. Permissions

Permissions are **atomic actions** (never tied directly to user types).  
Example categories:

| Category | Example Permissions |
|----------|---------------------|
| **batches** | `batches.create`, `batches.finish`, `batches.cancel`, `batches.view` |
| **inventory** | `inventory.adjust`, `inventory.view`, `inventory.edit`, `inventory.track_quantities` |
| **products** | `products.create`, `products.edit`, `products.manage_variants` |
| **organization** | `organization.manage_users`, `organization.manage_roles`, `organization.manage_billing` |
| **recipes** | `recipes.create`, `recipes.edit`, `recipes.plan_production`, `recipes.scale` |
| **reports** | `reports.view`, `reports.export`, `reports.advanced` |
| **settings** | `settings.edit`, `settings.view` |

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
| **Exempt Plan** | Unlimited | All permissions (internal/developer use) |
| **Free Tools** | 1 | Basic recipes and inventory view |
| **Solo Maker** | 1 | Full batch, inventory, and production features |
| **Team Plan** | 10 | All features including custom roles and team management |
| **Enterprise Plan** | Unlimited | All features, API integration |

✅ **Inactive users do NOT count toward subscription limits.**

---

## 5. Add-ons & Entitlements

Add-ons extend subscription tiers with optional permissions or feature toggles.

- **Permission add-ons** (`permission_name`) are granted only when the add-on is included on the tier or purchased.
- **Function-key add-ons** (`function_key`) are enforced in service logic (no RBAC permission).
- Tier permission pickers hide add-on permissions until the add-on is selected.

See [ADDONS_AND_ENTITLEMENTS.md](ADDONS_AND_ENTITLEMENTS.md) for the full workflow and update scripts.

---

## 6. User Management Workflow

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

## 7. Developer Deletion Modes (Support/Test Accounts)

Developer tooling now uses two explicit deletion behaviors for customer accounts:

- **Soft delete** (`/developer/api/user/soft-delete`): disables access and deactivates role assignments while preserving all historical records.
- **Hard delete** (`/developer/api/user/hard-delete`): permanently removes one non-developer user after clearing foreign-key references to avoid cross-table breakage.

For organization hard-delete (`/developer/organizations/<org_id>/delete`), the platform first archives marketplace/listed/sold recipe snapshots to JSON and detaches cross-organization lineage/source links before deleting org-scoped data.

✅ **Intended use**: controlled cleanup of test/support accounts by developers only.

---

## 8. Data Scoping Rules

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

## 9. Permission Checking

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

## 10. Best Practices

✔ Developers NEVER receive roles or organization IDs.  
✔ Always filter by `organization_id` for customer data.  
✔ Org Owners always have all tier-allowed permissions (don't reassign manually).  
✔ Only Team Members are role-limited.  
✔ All permissions must be stored in DB, no hardcoding.