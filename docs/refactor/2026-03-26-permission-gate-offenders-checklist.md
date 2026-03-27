# Permission Gate Offenders Checklist (2026-03-26)

## Synopsis
Single source-of-truth checklist for permission-boundary offenders. Use this file to track remediation progress exactly like the boundary extraction checklist.

## Glossary
- **Permission gate**: Route/service authorization enforced by `@require_permission(...)` or `@any_permission_required(...)` plus canonical permission checks.
- **Offender**: A route/service/template pattern that bypasses or duplicates canonical permission policy.
- **Canonical enforcement**: `docs/system/ROUTE_ACCESS_CONTROL.md` + `app/utils/permissions.py` decorator and permission APIs.

---

## Proper enforcement standard (what "correct" means now)

1. **All non-public routes use permission decorators**
   - Required: `@require_permission(...)` or `@any_permission_required(...)`.
   - Audit command: `FLASK_ENV=testing PYTHONPATH=/workspace python scripts/audit_route_permissions.py`.

2. **Authorization decisions are permission-based, not persona-string based**
   - Do not gate capabilities by `user_type == ...`, `role.name == ...`, or `has_role(...)` inside route/service logic.
   - Use permission checks and the canonical denied response path from `app/utils/permissions.py`.

3. **`user_type` is for context/scope resolution only**
   - Acceptable: selecting effective organization context for developer masquerade.
   - Not acceptable: granting or denying business actions because a user is `developer`/`customer`.

4. **Owner-only behavior must be explicit and consistent**
   - Prefer dedicated permission keys over ad-hoc owner checks.
   - If owner invariants are temporarily required, keep them centralized and documented (not repeated route-by-route).

5. **Only valid `user_type` values are `developer` and `customer`**
   - Eliminate `team_member` and `organization_owner` as `user_type` values/usages.
   - Organization owner is represented via `customer` + `is_organization_owner` + owner role.

6. **Templates use permission-driven display rules**
   - Prefer `has_permission(...)` driven flags from template context.
   - Avoid template authz via `has_role(...)` and raw `current_user.user_type` checks.

7. **Legacy auth decorators are migration targets**
   - `role_required`, `tier_required`, `require_organization_owner`, `require_system_admin`, and compatibility wrappers are not the end-state for route authz.

---

## Comprehensive offender inventory (check off as fixed)

### A) High-priority route/service policy offenders

#### Progress notes

- [x] **Phase 1A complete (this pass):** invalid `user_type` literals normalized in
  `organization` + `organization_route_service` + `user_invite_service`.
  - Removed `user_type="team_member"` writes (now `customer`).
  - Removed `user_type=="organization_owner"` checks in org routes; replaced with
    owner helper predicates.

- [x] **Phases 2-15 complete (current pass):** route-level persona drift reduced
  across the main offender set (`global_library`, `developer/decorators`,
  `affiliate_service`, `inventory`, `conversion`, `recipes/form_templates`,
  `recipe_library`, `settings`, `dashboard`, `core`, `api`, `products`,
  `auth/verification_routes`).
  - Route/service policy cleanup in this tracked offender set is complete.

- [x] `app/blueprints/organization/routes.py`
  - Repeated permission duplication with `user_type`/owner checks in routes already permission-decorated.
  - [x] Invalid `user_type` values/branches: `"organization_owner"` checks and `"team_member"` assignment.
  - [x] Role-name authorization in route logic (`role.name in ["developer", "organization_owner"]`) removed from route branch checks.

- [x] `app/services/organization_route_service.py`
  - [x] Invalid `user_type="team_member"` writes and reads.
  - Mixed capability gating by owner/developer persona for settings mutation.
  - Role-name checks in service authorization branch.

- [x] `app/blueprints/auth/permissions.py`
  - [x] Role-management authority split by `current_user.user_type` normalized through local helper checks.
  - [x] System-role and cross-org update branches keyed on persona string normalized through local helper checks.

- [x] `app/blueprints/global_library/routes.py`
  - [x] Manual permission metadata tagging (`_tag_required_permissions`) + inline `has_permission(...)` path replaced with canonical decorator usage.

- [x] `app/blueprints/developer/decorators.py`
  - [x] `require_developer_permission(...)` now delegates to canonical `permission_required(...)` without extra route-local persona gate logic.

- [x] `app/services/user_invite_service.py`
  - Role-name authorization check (`developer`/`organization_owner`) instead of permission-model authority.
  - [x] Invalid `user_type="team_member"` assignment.

- [x] `app/services/affiliate_service.py`
  - [x] Customer-only gate via `user.user_type != "customer"` replaced with organization-context checks.

### B) Route-level persona-gate drift (permission bypass/duplication risk)

- [x] `app/blueprints/inventory/routes.py`
  - [x] `can_edit_inventory_item(...)` now uses effective organization context instead of blanket developer bypass.

- [x] `app/blueprints/conversion/routes.py`
  - [x] Unit/mapping management branches now use effective organization context helper instead of inline developer persona conditionals.

- [x] `app/blueprints/recipes/form_templates.py`
  - [x] Sharing/purchase controls now rely on permission entitlements only (developer persona bypass removed).

- [x] `app/blueprints/recipe_library/routes.py`
  - [x] `reveal_details` now requires explicit support permission (`dev.all_organizations`) plus selected-org context.

- [x] `app/blueprints/settings/routes.py`
  - [x] Affiliate tab visibility and profile save redirects now use permission/context checks (persona branches removed).

- [x] `app/blueprints/dashboard/routes.py`
  - [x] Dashboard/fault-log organization selection now uses effective organization context helper (no inline developer persona route branches).

- [x] `app/blueprints/core/routes.py`
  - [x] Authenticated landing-route split now uses permission check (`dev.dashboard`) instead of persona string.

- [x] `app/blueprints/api/routes.py`
  - [x] Organization scope resolver now uses `get_effective_organization_id()` helper instead of inline persona branch.

- [x] `app/blueprints/products/products.py`
  - [x] Fallback import path removed; canonical `require_permission` import is now required.

- [x] `app/blueprints/auth/verification_routes.py`
  - [x] Post-verify redirect now uses permission-based routing (`dev.dashboard`) instead of persona string.

### C) Template authorization offenders (UX policy drift)

- [x] `app/templates/settings/index.html`
- [x] `app/templates/components/layout/navbar_authenticated_customer.html`
- [x] `app/templates/components/layout/navbar.html`
- [x] `app/templates/layout.html`
- [x] `app/templates/pages/auth/roles.html`
- [x] `app/templates/settings/components/affiliate_tab.html`
- [x] `app/templates/settings/components/billing_tab.html`
- [x] `app/templates/components/layout/navbar_guest.html`
- [x] `app/templates/components/layout/navbar_authenticated_developer.html`
- [x] `app/templates/components/shared/public_marketing_header.html`
- [x] `app/templates/pages/public/pricing.html`
- [x] `app/templates/pages/public/landing_hormozi.html`
- [x] `app/templates/pages/public/landing_robbins.html`

### D) Legacy decorator/shim offenders (deprecation track)

- [x] `app/utils/permissions.py`
  - [x] `tier_required(...)`
  - [x] `role_required(...)`
  - [x] `require_permission_with_org_scoping(...)`
  - [x] `require_system_admin(...)`
  - [x] `require_organization_owner(...)`

---

## Full scan coverage ledger (all flagged files classified)

This ledger classifies every file currently flagged by repository scans for
permission-boundary-adjacent patterns.

### 1) Confirmed remediation scope in this program (offenders)

- `app/blueprints/organization/routes.py`
- `app/services/organization_route_service.py`
- `app/blueprints/auth/permissions.py`
- `app/blueprints/global_library/routes.py`
- `app/blueprints/developer/decorators.py`
- `app/services/user_invite_service.py`
- `app/services/affiliate_service.py`
- `app/blueprints/inventory/routes.py`
- `app/blueprints/conversion/routes.py`
- `app/blueprints/recipes/form_templates.py`
- `app/blueprints/recipe_library/routes.py`
- `app/blueprints/settings/routes.py`
- `app/blueprints/dashboard/routes.py`
- `app/blueprints/core/routes.py`
- `app/blueprints/api/routes.py`
- `app/blueprints/products/products.py`
- `app/blueprints/auth/verification_routes.py`
- `app/templates/settings/index.html`
- `app/templates/components/layout/navbar_authenticated_customer.html`
- `app/templates/components/layout/navbar.html`
- `app/templates/layout.html`
- `app/templates/pages/auth/roles.html`
- `app/templates/settings/components/affiliate_tab.html`
- `app/templates/settings/components/billing_tab.html`
- `app/templates/components/layout/navbar_guest.html`
- `app/templates/components/layout/navbar_authenticated_developer.html`
- `app/templates/components/shared/public_marketing_header.html`
- `app/templates/pages/public/pricing.html`
- `app/templates/pages/public/landing_hormozi.html`
- `app/templates/pages/public/landing_robbins.html`
- `app/utils/permissions.py` (legacy wrappers/decorators section only)

### 2) Flagged by scan, but classified as contextual/expected (not checklist blockers)

- `app/blueprints/auth/login_routes.py` (auth/login flow routing and verification handling)
- `app/blueprints/auth/oauth_routes.py` (provider callback routing logic)
- `app/blueprints/onboarding/routes.py` (invite/onboarding workflow filtering; monitor)
- `app/blueprints/developer/views/user_routes.py` (developer admin transport layer; monitor for role-name gates)
- `app/services/developer/user_service.py` (developer admin business logic; monitor for migration opportunities)
- `app/services/settings_route_service.py` (preference segmentation by persona)
- `app/services/base_service.py` (effective-org context helper behavior)
- `app/template_context.py` (template/view-model context shaping)
- `app/utils/template_filters.py` (template helper behavior)
- `app/authz.py` (session/user-loader and login-manager concerns, not route capability gates)

### 3) Flagged by scan, data model/seed layer (not route permission-gate remediation)

- `app/models/models.py`
- `app/models/mixins.py`
- `app/models/statistics.py`
- `app/models/user_preferences.py`
- `app/services/signup_service.py`
- `app/services/auth_login_route_service.py`
- `app/services/developer/organization_service.py`
- `app/services/statistics/analytics_service.py`
- `app/seeders/user_seeder.py`

Notes:
- This section exists to ensure the inventory is complete and auditable.
- If policy changes require these files to be remediated, promote them into the
  check-off sections above.

---

## Program order (recommended fix sequence)

1. **Normalize invalid `user_type` usage first**
   - Remove `"team_member"` writes and `"organization_owner"` user_type checks.
2. **Fix `organization` + `auth/permissions` route authority next**
   - Highest concentration of duplicated/bypassing auth logic.
3. **Migrate manual/parallel gate patterns**
   - `global_library` manual permission tagging and `developer/decorators.py` parallel checks.
4. **Convert remaining route persona branches**
   - Inventory/conversion/recipe/settings/dashboard/core/api paths.
5. **Clean templates to permission-driven visibility only**
   - Remove `has_role(...)` and persona-string UI auth checks.
6. **Retire legacy decorators/shims**
   - After all callsites are migrated and parity is verified.

---

## Re-audit commands

- Route coverage and permission catalog integrity:
  - `FLASK_ENV=testing PYTHONPATH=/workspace python scripts/audit_route_permissions.py`
- Persona/role anti-pattern scan:
  - `rg 'current_user\.user_type|user\.user_type|is_organization_owner|has_role\(|role\.name|role_required|tier_required|require_organization_owner|require_system_admin|_tag_required_permissions' app -g '*.py'`
- Template authz drift scan:
  - `rg 'has_role\(|current_user\.user_type|current_user\.is_organization_owner' app/templates -g '*.html'`

