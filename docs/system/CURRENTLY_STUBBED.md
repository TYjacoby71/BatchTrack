# Currently Stubbed and Placeholder Implementations

This document consolidates stubs, placeholders, no-ops, and partially implemented areas across the app. Use it to prioritize hardening work pre‑launch.

## Integrations

- Whop billing provider [STUBBED]
  - Files: `app/services/billing_service.py`, `app/services/whop_service.py`, `app/blueprints/auth/routes.py` (whop_login route)
  - Notes: Pricing, checkout, webhook handling are stubbed; logs warn integration is disabled.

- POS/Shopify linkage [PARTIAL/STUBBED]
  - Files: `app/services/pos_integration.py`
  - Notes: Service routes reservations/sales to canonical inventory adjustment, but contains mocked classes and placeholders at bottom; should be refactored to real models and removed mocks. Shopify naming appears in notes/parameters but no direct Shopify API client.

## Inventory/FIFO/Conversion

- FIFO compatibility functions [STUBS]
  - Files: `app/blueprints/fifo/__init__.py`
  - Notes: Backward-compat exports raise `NotImplementedError`. Canonical path is `app/services/inventory_adjustment`.

- Inventory alerts shim [NO‑OP]
  - Files: `app/services/inventory_alerts.py`
  - Notes: Kept for compatibility; points to `combined_inventory_alerts.py` for real behavior.

- Unit conversion special op [PLACEHOLDER]
  - Files: `app/services/inventory_adjustment/_special_ops.py`
  - Notes: `handle_unit_conversion` marked as placeholder; complex paths still to be implemented or delegated to ConversionEngine fully.

## Developer/Admin

- Developer inventory analytics page [STUB]
  - Files: `app/blueprints/developer/routes.py` (`inventory_analytics_stub`), `app/templates/developer/inventory_analytics.html`

- Decorator fallbacks [PLACEHOLDER]
  - Files: `app/blueprints/developer/routes.py`
  - Notes: Placeholder `require_developer_permission` and `permission_required` defined when imports fail.

- Recipe library customer-facing detail view [PARTIAL]
  - Files: `app/blueprints/recipe_library/routes.py`, `app/templates/library/recipe_detail.html`
  - Notes: Developer/org view shows blurred sections; customer-facing unblur still needs UI.

## Permissions & Roles

- Role checking decorator [TODO/PLACEHOLDER]
  - Files: `app/utils/permissions.py` (`role_required`)
  - Notes: TODO indicates proper role checking not yet implemented (currently allows if authenticated in non‑test).

## Organization & Users

- Invite email dispatch [IMPLEMENTED]
  - Files: `app/services/user_invite_service.py`, `app/blueprints/organization/routes.py`
  - Notes: `UserInviteService.invite_user()` sends a password-setup email via `EmailService` when configured; falls back to manual password setup when email is not configured.

## Statistics / Warehouse / Reporting

- Developer “inventory analytics” UI [STUB]
  - Files: `app/blueprints/developer/routes.py` (as above)

- Modular statistics services [IMPLEMENTED]
  - Files: `app/services/statistics/*`
  - Notes: Core batch/inventory/recipe stats implemented; not stubs.

## Migrations (temporary/no‑op)

- No‑op/placeholder migrations
  - Files: `migrations/versions/add_email_verified_at_column.py` (no‑op), `migrations/versions/add_legacy_compatibility_fields.py` (no‑op), `migrations/versions/132971c1d456_add_all_missing_columns_to_match_model_.py` (TODO to add constraints later)

## Tests (guides/placeholders)

- TODOs and placeholders
  - Files: `tests/test_product_sku.py` (TODO add SKU creation test), `tests/test_stripe_webhooks.py` (TODO interface standardization), `tests/test_google_oauth.py` (TODO interface standardization), `tests/test_audit_canonicalization.py` (placeholder header)

## Marketing Content

- Pricing placeholder
  - Files: `marketing/content/pages/index.mdx` (Pricing section marked as placeholder)

---

## Recommended Hardening Tasks

1. Replace mocks in `app/services/pos_integration.py` with real model imports; remove dummy classes.
2. Implement `role_required` with real role checks; audit routes using it.
3. Wire Whop integration or gate it behind feature flags; update `billing_service` branches.
4. If needed, expand `handle_unit_conversion` or fully route via `ConversionEngine` and remove placeholder.
5. Convert developer decorator fallbacks into required imports; fail fast in prod builds.
6. Convert roadmap placeholders into tracked issues; add test coverage for stubs once implemented.

## Legend

- STUB: Functionality present as scaffold but not implemented; may raise or return dummy data.
- PARTIAL: Some end‑to‑end behavior exists but relies on placeholders or mocks.
- NO‑OP: Intentional stub maintaining compatibility without functional behavior.
- TODO: Commented work item in code indicating missing implementation.

