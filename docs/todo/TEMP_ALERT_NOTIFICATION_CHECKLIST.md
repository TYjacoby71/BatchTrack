# Temporary Alert / Notification Checklist

## Purpose
Audit current notification emitters, classify each source, assign priority, and mark whether each source is using the correct UX pattern.

## Status keys
- `done`: Current implementation type is acceptable for the use case.
- `incorrect`: Current implementation should be migrated to a different notification type.

## Priority keys
- `P1`: High priority inconsistency or disruptive UX.
- `P2`: Medium priority inconsistency.
- `P3`: Low priority / acceptable as-is.

## Checklist (A-F + priority)
| F: ID | A: Name | B: Current Type | C: Correct Type | D: Status | Priority | E: Create/Update Docs |
|---|---|---|---|---|---|---|
| ALRT-001 | `app/static/js/production_planning/modules/stock-check.js` (2 `alert()` calls) | Shared inline app alert helper (`window.showAlert`) | Inline app alert/toast (non-blocking) | done | P1 | Yes |
| ALRT-002 | `app/static/js/production_planning/modules/batch-management.js` (3 `alert()` calls) | Bootstrap modal for blocking + shared inline app alert helper | Bootstrap modal for blocking states; inline app alert for errors | done | P1 | Yes |
| ALRT-003 | `app/static/js/core/DrawerProtocol.js` (1 `alert()` fallback) | Shared inline app alert helper + drawer telemetry event | Standard inline app alert fallback + drawer telemetry | done | P1 | Yes |
| ALRT-004 | `app/static/js/batches/batch_form.js` (3 `alert()` calls) | Shared inline app alert helper (`window.showAlert`) | Shared notification helper (inline alert/toast) | done | P1 | Yes |
| ALRT-005 | `app/static/js/expiration_alerts.js` (2 `confirm()` calls) | Shared confirmation modal helper (`window.showConfirmDialog`) with native fallback | Confirmation modal (destructive action) | done | P1 | Yes |
| ALRT-006 | `app/static/js/inventory/inventory_view.js` (1 `confirm()` call) | Shared confirmation modal helper (`window.showConfirmDialog`) with native fallback | Confirmation modal (inventory-impacting action) | done | P1 | Yes |
| ALRT-007 | `app/static/js/batches/batch_form.js` (2 `confirm()` calls) | Shared confirmation modal helper (`window.showConfirmDialog`) with native fallback | Confirmation modal (batch lifecycle actions) | done | P1 | Yes |
| ALRT-008 | `app/static/js/settings.js` (3 `alert()` calls) | Shared inline app alert helper (`window.showAlert`) | Shared notification helper (inline alert/toast) | done | P2 | Yes |
| ALRT-009 | `app/static/js/inventory/inventory_adjust.js` (2 `alert()` validation calls) | Inline field validation + shared inline app alert helper | Inline field validation + inline app alert | done | P2 | Yes |
| ALRT-010 | `app/static/js/production_planning/modules/manual-container-mode.js` (2 `alert()` calls) | Shared inline app alert helper (`window.showAlert`) | Inline card/form warning | done | P2 | Yes |
| ALRT-011 | `app/static/js/conversion/unit_converter.js` (1 `alert()` copy confirmation) | Shared toast helper (`window.showToast`) | Toast ("copied") | done | P2 | Yes |
| ALRT-012 | `app/static/js/organization/dashboard.js` (5 `confirm()` calls) | Shared confirmation modal helper (`window.showConfirmDialog`) | Confirmation modal for destructive/role actions | done | P2 | Yes |
| ALRT-013 | `app/static/js/conversion/unit_converter.js` (1 `confirm()` decision flow) | Shared confirmation modal helper (`window.showConfirmDialog`) | Decision modal/drawer | done | P2 | Yes |
| ALRT-014 | `app/static/js/subscription_tiers.js` (fallback `alert`) | Shared notification helper only (console fallback) | Shared notification helper only | done | P2 | Yes |
| ALRT-015 | `app/static/js/products/product_inventory.js` (fallback `alert`) | Shared notification/toast helper only (console fallback) | Shared notification helper only | done | P2 | Yes |
| ALRT-016 | `app/static/js/main.js` global `showAlert()` | Bootstrap inline dismissible alert | Shared baseline in-app notification helper | done | P3 | Yes |
| ALRT-017 | `app/static/js/organization/dashboard.js` custom `showToast()` | Wrapper to shared toast helper (`window.showToast`) | Shared toast helper | done | P2 | Yes |
| ALRT-018 | `app/static/js/organization/dashboard.js` custom `showMessage()` | Wrapper to shared notification helper (`window.showAlert`) | Shared notification helper | done | P2 | Yes |
| ALRT-019 | `app/static/js/expiration_alerts.js` custom `showAlert()` | Wrapper to shared inline app alert helper | Shared notification helper | done | P2 | Yes |
| ALRT-020 | `app/static/js/tools/soaps/soap_tool_ui.js` (`showAutosaveToast`, `showUndoToast`, `showSoapAlert`) | Bootstrap toasts + inline alert stack | Correct for feature-local workflow | done | P3 | No |
| ALRT-021 | `app/static/js/production_planning/modules/batch-management.js` (`showSuccessMessage`/`showErrorMessage`) | Shared inline app alert helper | Shared notification helper | done | P2 | Yes |
| ALRT-022 | `app/templates/pages/production_planning/plan_production.html` (`#insufficientStockModal`) | Bootstrap confirmation modal | Correct for override decision | done | P3 | No |
| ALRT-023 | `app/templates/components/layout/content_chrome.html` flash renderer | Flask flash rendered as Bootstrap alerts | Correct global flash presentation | done | P3 | No |
| ALRT-024 | `app/templates/pages/auth/login.html` local flash renderer | Global flash renderer via layout chrome | Prefer global flash renderer unless auth-specific rationale | done | P3 | Yes |
| ALRT-025 | `app/templates/conversion/units.html` local flash renderer | Global flash renderer via layout chrome | Prefer global flash renderer unless page-specific rationale | done | P3 | Yes |
| ALRT-026 | Flask `flash()` sources in `app/utils/permissions.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-027 | Flask `flash()` sources in `app/resilience.py` (1) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-028 | Flask `flash()` sources in `app/middleware/guards.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-029 | Flask `flash()` sources in `app/middleware/registry.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-030 | Flask `flash()` sources in `app/blueprints/recipes/views/lineage_routes.py` (3) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-031 | Flask `flash()` sources in `app/blueprints/recipes/views/create_routes.py` (45) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-032 | Flask `flash()` sources in `app/blueprints/recipes/views/manage_routes.py` (35) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-033 | Flask `flash()` sources in `app/blueprints/organization/routes.py` (13) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-034 | Flask `flash()` sources in `app/blueprints/settings/routes.py` (18) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-035 | Flask `flash()` sources in `app/blueprints/products/sku.py` (12) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-036 | Flask `flash()` sources in `app/blueprints/products/products.py` (16) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-037 | Flask `flash()` sources in `app/blueprints/products/product_inventory_routes.py` (12) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-038 | Flask `flash()` sources in `app/blueprints/products/product_variants.py` (20) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-039 | Flask `flash()` sources in `app/blueprints/production_planning/routes.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-040 | Flask `flash()` sources in `app/blueprints/recipe_library/routes.py` (2) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-041 | Flask `flash()` sources in `app/blueprints/onboarding/routes.py` (10) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-042 | Flask `flash()` sources in `app/blueprints/conversion/routes.py` (18) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-043 | Flask `flash()` sources in `app/blueprints/bulk_stock/routes.py` (11) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-044 | Flask `flash()` sources in `app/blueprints/auth/verification_routes.py` (11) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-045 | Flask `flash()` sources in `app/blueprints/auth/whop_routes.py` (3) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-046 | Flask `flash()` sources in `app/blueprints/auth/password_routes.py` (7) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-047 | Flask `flash()` sources in `app/blueprints/auth/login_routes.py` (23) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-048 | Flask `flash()` sources in `app/blueprints/auth/oauth_routes.py` (21) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-049 | Flask `flash()` sources in `app/blueprints/auth/signup_routes.py` (2) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-050 | Flask `flash()` sources in `app/blueprints/global_library/routes.py` (6) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-051 | Flask `flash()` sources in `app/blueprints/inventory/routes.py` (17) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-052 | Flask `flash()` sources in `app/blueprints/auth/whop_auth.py` (3) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-053 | Flask `flash()` sources in `app/blueprints/billing/routes.py` (42) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-054 | Flask `flash()` sources in `app/blueprints/dashboard/routes.py` (5) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-055 | Flask `flash()` sources in `app/blueprints/developer/subscription_tiers.py` (43) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-056 | Flask `flash()` sources in `app/blueprints/developer/views/organization_routes.py` (4) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-057 | Flask `flash()` sources in `app/blueprints/developer/views/reference_routes.py` (14) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-058 | Flask `flash()` sources in `app/blueprints/developer/views/affiliate_routes.py` (18) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-059 | Flask `flash()` sources in `app/blueprints/developer/views/product_category_routes.py` (8) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-060 | Flask `flash()` sources in `app/blueprints/batches/start_batch.py` (6) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-061 | Flask `flash()` sources in `app/blueprints/developer/views/user_routes.py` (1) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-062 | Flask `flash()` sources in `app/blueprints/batches/cancel_batch.py` (4) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-063 | Flask `flash()` sources in `app/blueprints/developer/views/global_item_routes.py` (11) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-064 | Flask `flash()` sources in `app/blueprints/batches/finish_batch.py` (6) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-065 | Flask `flash()` sources in `app/blueprints/developer/views/analytics_routes.py` (1) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-066 | Flask `flash()` sources in `app/blueprints/batches/routes.py` (13) | Server flash message (explicit categories normalized) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-067 | Flask `flash()` sources in `app/blueprints/developer/views/masquerade_routes.py` (3) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-068 | Flask `flash()` sources in `app/blueprints/developer/decorators.py` (1) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-069 | Flask `flash()` sources in `app/blueprints/developer/addons.py` (8) | Server flash message (explicit categories validated) | Correct post-redirect messaging | done | P3 | Yes |
| ALRT-070 | `app/resilience.py` global HTTP error handlers (`404`, `500`, DB `503`) | Structured HTTP error responses (HTML pages + JSON payloads) | Dedicated full-page/system error responses by status code | done | P3 | Yes |
| ALRT-071 | `app/resilience.py` CSRF failure flow (`400` JSON or flash + redirect) | Context-aware API JSON error or server flash + 303 redirect | Same (API payload for XHR/API; flash+redirect for browser form flow) | done | P3 | Yes |
| ALRT-072 | `app/templates/components/layout/content_chrome.html` global unverified-email reminder banner | Shared inline warning alert with CTA actions | Shared inline warning alert in layout chrome | done | P2 | Yes |
| ALRT-073 | `app/templates/components/layout/overlay_modals.html` feature-gate upgrade modal | Shared blocking Bootstrap modal | Shared blocking modal for plan-gated actions | done | P2 | Yes |
| ALRT-074 | `app/templates/components/layout/overlay_modals.html` verification-required modal | Shared blocking Bootstrap modal (`static` backdrop) | Shared blocking modal for account-verification lock flow | done | P2 | Yes |
| ALRT-075 | `app/blueprints/tools/routes.py` tools draft quota-limit response (`429`, `limit_reached`) | Structured API quota/rate-limit JSON payload | Structured API quota payload consumed by client notifications | done | P2 | Yes |
| ALRT-076 | `app/blueprints/api/routes.py` BatchBot quota/service errors (`429`, `502`, `500`) | Structured API error JSON payloads | Structured API error payloads mapped to in-app UI messaging | done | P2 | Yes |
| ALRT-077 | `app/static/js/tools/soaps/soap_tool_events_exports.js` pop-up-blocked print warning | Feature-local inline alert stack (`showSoapAlert`) | Inline warning alert for blocked browser pop-up action | done | P3 | Yes |
| ALRT-078 | `app/templates/errors/404.html`, `app/templates/errors/500.html`, `app/templates/errors/maintenance.html` | Dedicated status-page card UI (not toast/inline flash) | Dedicated status-page UX for hard navigation/server faults | done | P3 | Yes |
| ALRT-079 | `app/templates/billing/upgrade.html` debug-only billing status banner | Inline informational alert (`alert-info`) | Inline informational debug callout (dev-only) | done | P3 | Yes |
| ALRT-080 | `app/middleware/registry.py` security/bot blocked responses (`403`) | Plain `403` text or JSON error payload (non-toast) | Security response payload/page (not standard toast/modal) | done | P3 | Yes |
| ALRT-081 | `app/static/js/main.js` native `alert()` compatibility shim retirement | Legacy `alert(...)` compatibility shim removed after source migration | No shim required; source paths call shared helpers directly | done | P1 | Yes |
| ALRT-082 | `app/static/js/main.js` global prompt + declarative confirm infrastructure | Shared `showPromptDialog(...)` + `data-confirm-message` submit/click handling | Shared modal/prompt framework for blocking confirmations/input | done | P1 | Yes |
| ALRT-083 | Inline confirm attributes migrated (`conversion/units`, inventory archive links, tier/addon/category delete forms, SKU merge form) | Declarative confirm attributes (`data-confirm-*`) | Shared modal confirmation pipeline (no inline native confirm) | done | P1 | Yes |
| ALRT-084 | Scripted native confirm/prompt migrations (`admin/reservations`, `recipe_form`, inventory/product expiration flows, `system_roles`, `user_management_modal`, `timer_list`, `bulk_updates`) | Async shared `showConfirmDialog`/`showPromptDialog` usage with guarded fallbacks | Shared modal/prompt helpers in runtime JS flows | done | P1 | Yes |
| ALRT-085 | Pop-up blocked coverage for `window.open(...)` callsites (`DrawerProtocol`, org dashboard exports, user support/session-open flows, density/global-item reference links) | Shared `openWindowOrNotify(...)` helper + warning alert fallback | Unified pop-up blocked notification behavior | done | P2 | Yes |
| ALRT-086 | Lightweight public shell script loading (`scripts_primary.html`) | Loads shared notification runtime (`main.js`) in lightweight mode | Consistent global notification API availability across shells | done | P2 | Yes |
| ALRT-087 | Notification primitive drift guard (`scripts/validate_notification_primitives.py` + workflow step) | Diff-based guard against new native dialog primitives | Prevent future notification-pattern regressions | done | P2 | Yes |
| ALRT-088 | Template/native alert elimination pass (`app/templates/**`, source JS/HTML/Jinja) | Remaining direct native `alert(...)` callsites in source templates | Shared notification helper usage (`window.showAlert`) with shim no longer installed | done | P1 | Yes |

## Compiled priority queue (from checklist)
### P1 (highest)
- ALRT-001, ALRT-002, ALRT-003, ALRT-004, ALRT-005, ALRT-006, ALRT-007, ALRT-081, ALRT-082, ALRT-083, ALRT-084, ALRT-088

### P2
- ALRT-008, ALRT-009, ALRT-010, ALRT-011, ALRT-012, ALRT-013, ALRT-014, ALRT-015, ALRT-017, ALRT-018, ALRT-019, ALRT-021, ALRT-072, ALRT-073, ALRT-074, ALRT-075, ALRT-076, ALRT-085, ALRT-086, ALRT-087

### P3
- ALRT-016, ALRT-020, ALRT-022, ALRT-023, ALRT-024, ALRT-025, ALRT-026 through ALRT-071, ALRT-077 through ALRT-080

## Notes
- This list is generated from current source emitters (JS `alert`/`confirm`, JS notification helpers, and Python `flash` callsites).
- Built assets under `app/static/dist/` are intentionally excluded from classification to avoid duplicate entries.
- Phase-1 implementation pass complete for ALRT-001 through ALRT-010.
- Phase-2 implementation pass complete for ALRT-011 through ALRT-030.
- Phase-3 implementation pass complete for ALRT-031 through ALRT-040.
- Phase-4 implementation pass complete for ALRT-041 through ALRT-050.
- Phase-5 implementation pass complete for ALRT-051 through ALRT-069.
- Phase-6 inventory extension complete for ALRT-070 through ALRT-080 (system-level handlers, shared overlays, and API quota/error payload surfaces).
- Phase-7 native-dialog normalization complete for ALRT-081 through ALRT-087 (shared alert/prompt compatibility layer, declarative confirms, migrated scripted confirm/prompt flows, pop-up blocked helper, and drift-prevention guard).
- Phase-8 legacy alert elimination complete for ALRT-088 (source-template native `alert(...)` callsites migrated to `window.showAlert(...)` and `main.js` shim installation retired).
