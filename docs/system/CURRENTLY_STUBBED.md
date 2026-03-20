# Currently Stubbed and Placeholder Implementations

This document consolidates stubs, placeholders, no-ops, and partially implemented areas across the app.

Audit status: refreshed from repository scan on 2026-03-20.

## Integrations

- Whop billing provider [PARTIAL/STUBBED]
  - Files: `app/services/billing_service.py`, `app/services/whop_service.py`, `app/blueprints/auth/whop_routes.py`, `app/blueprints/auth/whop_auth.py`
  - Notes: Whop login/license validation path exists, but checkout/pricing/cancel helpers are stubbed and `BillingService.handle_webhook_event(..., provider="whop")` logs "not yet implemented".
  - Tracking: Scheduled in `docs/todo/LAUNCH_HARDENING_CHECKLIST.md` Priority 5.1 (Whop webhook path or explicit disable).

- POS/Shopify linkage [PARTIAL/STUBBED]
  - Files: `app/services/pos_integration.py`
  - Notes: Core reservation/sale/return flow delegates to canonical inventory adjustment, but file still contains embedded mock/stub classes in production module footer.
  - Tracking: Not explicitly scheduled in `LAUNCH_HARDENING_CHECKLIST.md`; add explicit cleanup item to backlog/checklist.

- Soap Tool "Push to Recipes" action [STUBBED]
  - Files: `app/static/js/tools/soaps/soap_tool_events_exports.js`
  - Notes: UI confirms payload readiness but explicitly states push is stubbed and sends no data.
  - Tracking: Not explicitly scheduled in `CONSOLIDATED_BACKLOG.md`; add dedicated item if this feature is in scope.

## Inventory/FIFO/Conversion

- FIFO compatibility functions [STUBS]
  - Files: `app/blueprints/fifo/__init__.py`
  - Notes: Backward-compat exports raise `NotImplementedError`. Canonical path is `app/services/inventory_adjustment`.

- Inventory alerts shim [NO‑OP]
  - Files: `app/services/inventory_alerts.py`
  - Notes: Kept for compatibility; points to `combined_inventory_alerts.py` for real behavior.

- Unit conversion special op [IMPLEMENTED]
  - Files: `app/services/inventory_adjustment/_special_ops.py`
  - Notes: `handle_unit_conversion` now routes through `ConversionEngine`, validates conversion, and logs a no-op history event.

## Developer/Admin

- Developer inventory analytics page [IMPLEMENTED]
  - Files: `app/blueprints/developer/views/analytics_routes.py`, `app/templates/developer/inventory_analytics.html`
  - Notes: Route function name still contains `_stub` legacy naming, but page and data endpoints are implemented.

- Developer waitlist signups page [STUB]
  - Files: `app/blueprints/developer/routes.py` (`waitlist_signups_view`)
  - Notes: Returns `"Waitlist Signups - Not Implemented Yet"` placeholder text.
  - Tracking: Not explicitly scheduled in `CONSOLIDATED_BACKLOG.md`.

- Fault log landing page [STUB]
  - Files: `app/blueprints/faults/routes.py`
  - Notes: Placeholder response `"Fault log coming soon"` behind permission gate.
  - Tracking: Not explicitly scheduled in `CONSOLIDATED_BACKLOG.md`.

- Recipe library customer-facing detail view [PARTIAL]
  - Files: `app/blueprints/recipe_library/routes.py`, `app/templates/library/recipe_detail.html`
  - Notes: Developer/org view shows blurred sections; customer-facing unblur still needs UI.

## Permissions & Roles

- Role checking decorator [TODO/PLACEHOLDER]
  - Files: `app/utils/permissions.py` (`role_required`)
  - Notes: TODO indicates proper role checking not yet implemented (currently allows if authenticated in non‑test).
  - Tracking: Scheduled in `docs/todo/LAUNCH_HARDENING_CHECKLIST.md` Priority 4.3 (`role_required` TODO path removal).

## Organization & Users

- Invite email dispatch [IMPLEMENTED]
  - Files: `app/services/user_invite_service.py`, `app/blueprints/organization/routes.py`
  - Notes: `UserInviteService.invite_user()` sends a password-setup email via `EmailService` when configured; falls back to manual password setup when email is not configured.

- Account verification + onboarding gating [IMPLEMENTED]
  - Files: `app/services/email_service.py`, `app/models/user_lifecycle.py`, `app/middleware/guards.py`, `app/templates/components/layout/overlay_modals.html`
  - Notes: Verification token lifecycle, resend flows, and onboarding enforcement are wired.

## Statistics / Warehouse / Reporting

- Modular statistics services [IMPLEMENTED]
  - Files: `app/services/statistics/*`
  - Notes: Core batch/inventory/recipe stats implemented; not stubs.

## Migrations

- Prior references to missing migration files [STALE DOC FIXED]
  - Notes: Previously listed migration filenames no longer exist in `migrations/versions/`.
  - Current caveat: `migrations/versions/0021_recipe_lineage_backfill.py` has a no-op downgrade (`pass`) due to backfill irreversibility.

## Tests

- Prior references to missing test files [STALE DOC FIXED]
  - Notes: `tests/test_product_sku.py` and `tests/test_audit_canonicalization.py` are not present.
  - `tests/test_stripe_webhooks.py` and `tests/test_google_oauth.py` are active characterization/integration-style test files, not placeholders.

## Marketing Content

- Pricing placeholder
  - Files: `app/marketing/content/pages/index.mdx`
  - Notes: Section header is still explicitly marked `Pricing (placeholder)`.
  - Tracking: Related to launch messaging work in `docs/todo/CONSOLIDATED_BACKLOG.md` (waitlist email/template and marketing polish backlog).

---

## Recommended Hardening Tasks

1. Replace embedded mock classes in `app/services/pos_integration.py` with dedicated test fixtures and keep production module clean.
2. Implement `role_required` with real role checks (or remove and migrate callers to permission-based checks).
3. Complete Whop integration path (webhook + pricing/checkout) or enforce explicit runtime disable with hard failure in non-supported mode.
4. Replace developer waitlist-signups placeholder route with a real data-backed view (or remove route).
5. Implement real fault-log landing experience/API or explicitly deprecate the blueprint.
6. Implement Soap Tool "Push to Recipes" server workflow or hide the action behind feature gating until ready.
7. Complete customer-facing recipe detail unlock UX for authorized/purchased states.
8. Replace `app/marketing/content/pages/index.mdx` pricing placeholder with final copy and plan matrix.

## Legend

- STUB: Functionality present as scaffold but not implemented; may raise or return dummy data.
- PARTIAL: Some end‑to‑end behavior exists but relies on placeholders or mocks.
- NO‑OP: Intentional stub maintaining compatibility without functional behavior.
- TODO: Commented work item in code indicating missing implementation.

