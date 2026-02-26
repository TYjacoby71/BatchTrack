# Route Access Control Standard

## Synopsis
Defines the permission-based access control standard for all routes, including the developer route-to-permission mapping and the checklist for adding new routes.

## Glossary
- **Route permission**: A `@require_permission(...)` decorator binding a route to its access gate.
- **Developer permission**: A `dev.*` permission scoped to developer-only routes.

## Single source of truth
Permissions are the source of truth for access control:

- **Developer-only**: permission exists in `DeveloperPermission` (usually `dev.*`)
- **Customer-only**: permission exists in `Permission`
- **Shared**: permission exists in both

All non-public routes **must** declare a permission with
`@require_permission(...)` or `@any_permission_required(...)`. The middleware
uses these decorators to classify the route and enforce developer vs customer
access and organization selection.

## Standard behavior
- **Unauthorized**: redirect to login (or JSON 401).
- **Permission denied**: bounce back to the previous page with a flash message.
- **Upgrade available**: show a CTA button in the flash message and include
  `upgrade_url`/`upgrade_tiers` in JSON responses.

## Add a route (required checklist)
1. Add the permission to `consolidated_permissions.json` (dev or customer).
2. Seed permissions (or run seeder in the environment).
3. Decorate the route with `@require_permission(...)`.
4. Run the audit:
   ```bash
   python scripts/audit_route_permissions.py
   ```
5. Update this doc if the route is developer-facing.

## Developer route → permission mapping (100%)

### Core developer navigation
- `/developer/dashboard`, `/developer/batchley` → `dev.dashboard`
- `/developer/marketing-admin`, `/developer/marketing-admin/save` → `dev.system_admin`
- `/developer/system-settings`, `/developer/system-settings/update` → `dev.system_settings`
- `/developer/feature-flags` → `dev.system_admin`
- `/developer/system-statistics` → `dev.access_logs`
- `/developer/billing-integration` → `dev.view_all_billing`
- `/developer/waitlist-statistics` → `dev.system_admin`

### Customer support & org management
- `/developer/organizations`, `/developer/customer-support` → `dev.all_organizations`
- `/developer/organizations/create` → `dev.create_organizations`
- `/developer/organizations/<id>` → `dev.all_organizations`
- `/developer/organizations/<id>/edit` → `dev.modify_any_organization`
- `/developer/organizations/<id>/upgrade` → `dev.billing_override`
- `/developer/organizations/<id>/delete` → `dev.delete_organizations`
- `/developer/select-org/<id>`, `/developer/view-as-organization/<id>`,
  `/developer/clear-organization-filter` → `dev.all_organizations`

### User management & system roles
- `/developer/users` + `/developer/api/user/*` → `dev.manage_users`
- `/developer/api/developer-user/*` → `dev.manage_roles`
- `/developer/system-roles*` (all system role APIs) → `dev.manage_roles`
- `/auth/permissions*` → `dev.assign_permissions`

### Subscription, billing & add-ons
- `/developer/subscription-tiers*` → `dev.manage_tiers`
- `/developer/addons*` → `dev.manage_tiers`

### Integrations & environment tooling
- `/developer/integrations*` → `dev.system_admin`
- `/developer/debug/permissions`, `/developer/debug/tiers` → `dev.debug_mode`

### Global library & reference data
- `/developer/global-items*` → `dev.system_admin`
- `/developer/product-categories*` → `dev.system_admin`
- `/developer/reference-categories*`, `/developer/container-management*`,
  `/developer/ingredient-attributes*`, `/developer/api/container-options` → `dev.system_admin`

### Analytics
- `/developer/inventory-analytics`
- `/developer/api/inventory-analytics/*`
- `/developer/analytics-catalog`
- `/developer/api/stats`
→ `dev.access_logs`

### Marketing intake
- `/developer/vendor-signups`, `/developer/waitlist-signups` → `dev.dashboard`
- `/developer/api/vendor/signup` → `dev.dashboard`
