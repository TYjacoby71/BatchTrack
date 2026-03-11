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
| ALRT-001 | `app/static/js/production_planning/modules/stock-check.js` (2 `alert()` calls) | Native browser alert | Inline app alert/toast (non-blocking) | incorrect | P1 | Yes |
| ALRT-002 | `app/static/js/production_planning/modules/batch-management.js` (3 `alert()` calls) | Native browser alert | Bootstrap modal for blocking states; inline app alert for errors | incorrect | P1 | Yes |
| ALRT-003 | `app/static/js/core/DrawerProtocol.js` (1 `alert()` fallback) | Native browser alert | Standard inline app alert fallback + drawer telemetry | incorrect | P1 | Yes |
| ALRT-004 | `app/static/js/batches/batch_form.js` (3 `alert()` calls) | Native browser alert | Shared notification helper (inline alert/toast) | incorrect | P1 | Yes |
| ALRT-005 | `app/static/js/expiration_alerts.js` (2 `confirm()` calls) | Native browser confirm | Confirmation modal (destructive action) | incorrect | P1 | Yes |
| ALRT-006 | `app/static/js/inventory/inventory_view.js` (1 `confirm()` call) | Native browser confirm | Confirmation modal (inventory-impacting action) | incorrect | P1 | Yes |
| ALRT-007 | `app/static/js/batches/batch_form.js` (2 `confirm()` calls) | Native browser confirm | Confirmation modal (batch lifecycle actions) | incorrect | P1 | Yes |
| ALRT-008 | `app/static/js/settings.js` (3 `alert()` calls) | Native browser alert | Shared notification helper (inline alert/toast) | incorrect | P2 | Yes |
| ALRT-009 | `app/static/js/inventory/inventory_adjust.js` (2 `alert()` validation calls) | Native browser alert | Inline field validation + inline app alert | incorrect | P2 | Yes |
| ALRT-010 | `app/static/js/production_planning/modules/manual-container-mode.js` (2 `alert()` calls) | Native browser alert | Inline card/form warning | incorrect | P2 | Yes |
| ALRT-011 | `app/static/js/conversion/unit_converter.js` (1 `alert()` copy confirmation) | Native browser alert | Toast ("copied") | incorrect | P2 | Yes |
| ALRT-012 | `app/static/js/organization/dashboard.js` (5 `confirm()` calls) | Native browser confirm | Confirmation modal for destructive/role actions | incorrect | P2 | Yes |
| ALRT-013 | `app/static/js/conversion/unit_converter.js` (1 `confirm()` decision flow) | Native browser confirm | Decision modal/drawer | incorrect | P2 | Yes |
| ALRT-014 | `app/static/js/subscription_tiers.js` (fallback `alert`) | Native alert fallback | Shared notification helper only | incorrect | P2 | Yes |
| ALRT-015 | `app/static/js/products/product_inventory.js` (fallback `alert`) | Native alert fallback | Shared notification helper only | incorrect | P2 | Yes |
| ALRT-016 | `app/static/js/main.js` global `showAlert()` | Bootstrap inline dismissible alert | Shared baseline in-app notification helper | done | P3 | Yes |
| ALRT-017 | `app/static/js/organization/dashboard.js` custom `showToast()` | Custom fixed-position alert-as-toast | Shared toast helper | incorrect | P2 | Yes |
| ALRT-018 | `app/static/js/organization/dashboard.js` custom `showMessage()` | Custom inline/fixed alerts | Shared notification helper | incorrect | P2 | Yes |
| ALRT-019 | `app/static/js/expiration_alerts.js` custom `showAlert()` | Local inline alert helper | Shared notification helper | incorrect | P2 | Yes |
| ALRT-020 | `app/static/js/tools/soaps/soap_tool_ui.js` (`showAutosaveToast`, `showUndoToast`, `showSoapAlert`) | Bootstrap toasts + inline alert stack | Correct for feature-local workflow | done | P3 | No |
| ALRT-021 | `app/static/js/production_planning/modules/batch-management.js` (`showSuccessMessage`/`showErrorMessage`) | Local inline alerts | Shared notification helper | incorrect | P2 | Yes |
| ALRT-022 | `app/templates/pages/production_planning/plan_production.html` (`#insufficientStockModal`) | Bootstrap confirmation modal | Correct for override decision | done | P3 | No |
| ALRT-023 | `app/templates/components/layout/content_chrome.html` flash renderer | Flask flash rendered as Bootstrap alerts | Correct global flash presentation | done | P3 | No |
| ALRT-024 | `app/templates/pages/auth/login.html` local flash renderer | Local flash rendering | Prefer global flash renderer unless auth-specific rationale | incorrect | P3 | Yes |
| ALRT-025 | `app/templates/conversion/units.html` local flash renderer | Local flash rendering | Prefer global flash renderer unless page-specific rationale | incorrect | P3 | Yes |
| ALRT-026 | Flask `flash()` sources in `app/utils/permissions.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-027 | Flask `flash()` sources in `app/resilience.py` (1) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-028 | Flask `flash()` sources in `app/middleware/guards.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-029 | Flask `flash()` sources in `app/middleware/registry.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-030 | Flask `flash()` sources in `app/blueprints/recipes/views/lineage_routes.py` (3) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-031 | Flask `flash()` sources in `app/blueprints/recipes/views/create_routes.py` (45) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-032 | Flask `flash()` sources in `app/blueprints/recipes/views/manage_routes.py` (35) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-033 | Flask `flash()` sources in `app/blueprints/organization/routes.py` (13) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-034 | Flask `flash()` sources in `app/blueprints/settings/routes.py` (18) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-035 | Flask `flash()` sources in `app/blueprints/products/sku.py` (12) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-036 | Flask `flash()` sources in `app/blueprints/products/products.py` (16) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-037 | Flask `flash()` sources in `app/blueprints/products/product_inventory_routes.py` (12) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-038 | Flask `flash()` sources in `app/blueprints/products/product_variants.py` (20) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-039 | Flask `flash()` sources in `app/blueprints/production_planning/routes.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-040 | Flask `flash()` sources in `app/blueprints/recipe_library/routes.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-041 | Flask `flash()` sources in `app/blueprints/onboarding/routes.py` (10) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-042 | Flask `flash()` sources in `app/blueprints/conversion/routes.py` (18) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-043 | Flask `flash()` sources in `app/blueprints/bulk_stock/routes.py` (11) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-044 | Flask `flash()` sources in `app/blueprints/auth/verification_routes.py` (11) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-045 | Flask `flash()` sources in `app/blueprints/auth/whop_routes.py` (3) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-046 | Flask `flash()` sources in `app/blueprints/auth/password_routes.py` (7) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-047 | Flask `flash()` sources in `app/blueprints/auth/login_routes.py` (23) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-048 | Flask `flash()` sources in `app/blueprints/auth/oauth_routes.py` (21) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-049 | Flask `flash()` sources in `app/blueprints/auth/signup_routes.py` (2) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-050 | Flask `flash()` sources in `app/blueprints/global_library/routes.py` (6) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-051 | Flask `flash()` sources in `app/blueprints/inventory/routes.py` (17) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-052 | Flask `flash()` sources in `app/blueprints/auth/whop_auth.py` (3) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-053 | Flask `flash()` sources in `app/blueprints/billing/routes.py` (42) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-054 | Flask `flash()` sources in `app/blueprints/dashboard/routes.py` (5) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-055 | Flask `flash()` sources in `app/blueprints/developer/subscription_tiers.py` (43) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-056 | Flask `flash()` sources in `app/blueprints/developer/views/organization_routes.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-057 | Flask `flash()` sources in `app/blueprints/developer/views/reference_routes.py` (14) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-058 | Flask `flash()` sources in `app/blueprints/developer/views/affiliate_routes.py` (18) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-059 | Flask `flash()` sources in `app/blueprints/developer/views/product_category_routes.py` (8) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-060 | Flask `flash()` sources in `app/blueprints/batches/start_batch.py` (6) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-061 | Flask `flash()` sources in `app/blueprints/developer/views/user_routes.py` (1) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-062 | Flask `flash()` sources in `app/blueprints/batches/cancel_batch.py` (4) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-063 | Flask `flash()` sources in `app/blueprints/developer/views/global_item_routes.py` (11) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-064 | Flask `flash()` sources in `app/blueprints/batches/finish_batch.py` (6) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-065 | Flask `flash()` sources in `app/blueprints/developer/views/analytics_routes.py` (1) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-066 | Flask `flash()` sources in `app/blueprints/batches/routes.py` (13) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-067 | Flask `flash()` sources in `app/blueprints/developer/views/masquerade_routes.py` (3) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-068 | Flask `flash()` sources in `app/blueprints/developer/decorators.py` (1) | Server flash message | Correct post-redirect messaging | done | P3 | No |
| ALRT-069 | Flask `flash()` sources in `app/blueprints/developer/addons.py` (8) | Server flash message | Correct post-redirect messaging | done | P3 | No |

## Compiled priority queue (from checklist)
### P1 (highest)
- ALRT-001, ALRT-002, ALRT-003, ALRT-004, ALRT-005, ALRT-006, ALRT-007

### P2
- ALRT-008, ALRT-009, ALRT-010, ALRT-011, ALRT-012, ALRT-013, ALRT-014, ALRT-015, ALRT-017, ALRT-018, ALRT-019, ALRT-021

### P3
- ALRT-016, ALRT-020, ALRT-022, ALRT-023, ALRT-024, ALRT-025, ALRT-026 through ALRT-069

## Notes
- This list is generated from current source emitters (JS `alert`/`confirm`, JS notification helpers, and Python `flash` callsites).
- Built assets under `app/static/dist/` are intentionally excluded from classification to avoid duplicate entries.
