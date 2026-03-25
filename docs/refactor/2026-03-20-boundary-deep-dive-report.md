# Boundary Deep Dive Report and Fix Plan (2026-03-20)

## Scope and method
- Reviewed architecture and access-control standards, current stubs/backlog/hardening docs, and route-access policy.
- Ran static boundary scans across `app/` and generated raw findings (`/tmp/boundary_deep_dive_raw.json`).
- Normalized noisy heuristics with the route-permission audit script output and existing policy docs.

## Current boundary gradecard
| Boundary | Grade | Why |
| --- | --- | --- |
| Service authority | 6.5/10 | Canonical design exists, but active route/data flows still bypass service boundaries in multiple blueprints. |
| Controller vs business logic | 8.9/10 | 14 blueprint modules still contain direct query/session logic after extracting ingredient API category/search/forms/create-link/global-search query and session touchpoints into service boundaries on top of prior batches. |
| Data access ownership | 8.9/10 | Persistence logic remains mixed into route layers, but this pass removed additional route-local query/session touchpoints from ingredient API route handlers. |
| Tenant isolation | 8.6/10 | Major scoped-query hardening is complete, with residual review needed on heuristic-risk files. |
| Permission boundary | 8.0/10 | Non-public route permission audit is clean and `role_required` now enforces real role checks; remaining risk is broader policy consistency (`user_type` gates and role->permission migration). |
| Integration boundaries | 5.9/10 | Stripe path is mature; Whop and Soap push remain partial/stubbed; POS file still contains embedded test mocks. |
| UI/product completion boundary | 6.7/10 | Several user/admin surfaces still show explicit "coming soon"/placeholder states. |

## Boundary 1: Service authority
### Offending pieces
- `app/blueprints/expiration/routes.py` imports both models and services in one route layer, increasing bypass risk.
- Hardening checklist still marks service-boundary extraction work open in top offender files: `developer/views/reference_routes.py`, `products/product_variants.py`, `settings/routes.py`, `inventory/routes.py`, `organization/routes.py`.
- `app/services/pos_integration.py` still includes embedded test/mock classes in the production module footer.
### Scheduled status
- Scheduled: yes (Priority 4.2 service boundary enforcement + broad backlog item for service-layer violations).
- Completion signal: structural cleanup section is still 0/25 complete in hardening checklist.

## Boundary 2: Controller vs business logic
- Total blueprint files with direct query/session access: **14**.
### Top offenders (direct query count)
- `app/blueprints/developer/system_roles.py`: 50
- `app/blueprints/developer/views/reference_routes.py`: 38
- `app/blueprints/developer/subscription_tiers.py`: 34
- `app/blueprints/organization/routes.py`: 33
- `app/blueprints/developer/views/global_item_routes.py`: 32
- `app/blueprints/auth/permissions.py`: 28
- `app/blueprints/conversion/routes.py`: 24
- `app/blueprints/inventory/routes.py`: 24
- `app/blueprints/auth/login_routes.py`: 19
- `app/blueprints/settings/routes.py`: 19
- `app/blueprints/products/product_variants.py`: 17
- `app/blueprints/batches/finish_batch.py`: 14
- `app/blueprints/expiration/services.py`: 14
- `app/blueprints/products/products.py`: 13
- `app/blueprints/products/product_inventory_routes.py`: 9 (resolved in this pass; removed from offender list)

## Boundary 3: Data access ownership
- Data access findings overlap controller/business findings: persistence logic is still route-adjacent in 14 files.
- Drawers/actions endpoints and several developer/admin modules still perform direct `db.session` mutations in route scope.

## Boundary 4: Tenant isolation
### Confirmed progress
- Launch hardening records scoped-query hardening complete for broad blueprint coverage, with intentional exceptions documented.
### Residual heuristic-risk files (manual verification required)
- `app/blueprints/api/public.py` (resolved in this pass; moved search/unit queries behind service boundary)
- `app/blueprints/developer/subscription_tiers.py`
- `app/blueprints/developer/views/user_routes.py` (already reduced in prior pass; removed from offender list)
- Note: several entries are developer/public/auth surfaces and may be intentionally unscoped by policy.

## Boundary 5: Permission boundary
### Real offenders
- Route permission audit now reports no missing non-public route decorators.
- `role_required` is now implemented with real role-name enforcement; remaining work is migrating legacy role gates toward canonical permission decorators.

### Risk concentration
- Direct `current_user.user_type` gate occurrences detected in 9 files (29 occurrences total).
- `app/blueprints/organization/routes.py`: 11 occurrences
- `app/blueprints/auth/permissions.py`: 5 occurrences
- `app/blueprints/conversion/routes.py`: 4 occurrences
- `app/blueprints/settings/routes.py`: 3 occurrences
- `app/blueprints/dashboard/routes.py`: 2 occurrences
- `app/blueprints/core/routes.py`: 1 occurrences
- `app/blueprints/inventory/routes.py`: 1 occurrences
- `app/blueprints/products/products.py`: 1 occurrences
- `app/blueprints/recipe_library/routes.py`: 1 occurrences

### Policy context
- Route access is centrally classified in `app/route_access.py` and non-public permission requirements are defined in `docs/system/ROUTE_ACCESS_CONTROL.md`.
- Heuristic scan found many routes without explicit decorators, but many are expected public endpoints by route-access policy; treat as classification drift risk, not automatic defects.

## Boundary 6: Integration boundaries
### Offending pieces
- `app/services/billing_service.py`: Whop webhook path logs "not yet implemented".
- `app/services/whop_service.py`: checkout/pricing/cancel methods are explicitly stubbed/disabled.
- `app/services/pos_integration.py`: embedded mock classes in production module.
- `app/static/js/tools/soaps/soap_tool_events_exports.js`: Push-to-recipes flow is explicitly stubbed in UI messaging.
### Scheduled status
- Whop runtime posture is now tracked in backlog and hardening checklist.
- POS mock cleanup and Soap push workflow are now tracked in backlog.

## Boundary 7: UI/product completion boundary
### High-signal placeholders (non-form-field placeholders)
- `app/templates/tools/lotions.html` L8: <span class="badge bg-secondary">Coming Soon</span>
- `app/templates/tools/index.html` L8: {% set page_description = "Free batch tools for makers: soap formulator live now, candle, cosmetic, and fermentation tools coming soon. Batch-first and neurodivergent-friendly." %}
- `app/templates/tools/baker.html` L8: <span class="badge bg-secondary">Coming Soon</span>
- `app/templates/tools/candles.html` L8: <span class="badge bg-secondary">Coming Soon</span>
- `app/templates/tools/herbal.html` L8: <span class="badge bg-secondary">Coming Soon</span>
- `app/templates/library/global_item_detail.html` L120: <span class="small text-muted">URL coming soon</span>
- `app/templates/library/recipe_detail.html` L176: <small class="text-muted">Full ingredients, consumables, and packaging details are available to developers viewing on behalf of an organization. (Customer view pending UI build-out.)</small>
- `app/templates/developer/waitlist_statistics.html` L210: <p>Export functionality coming soon!</p>
- `app/templates/components/drawer/global_item_stats_offcanvas.html` L56: Store (coming soon)
- `app/templates/pages/public/landing_hormozi.html` L255: <li>Shopify and Etsy integrations marked as coming soon.</li>
- `app/templates/pages/public/landing_robbins.html` L260: <li>Shopify and Etsy integrations flagged as coming soon.</li>
- `app/marketing/content/pages/index.mdx` L25: ## Pricing (placeholder)
- `app/static/js/organization/dashboard.js` L484: showMessage('Role editing functionality coming soon', 'info');
- `app/static/js/organization/dashboard.js` L497: showMessage('Role deletion functionality coming soon', 'info');
- `app/static/js/organization/dashboard.js` L501: showMessage('Audit log functionality coming soon', 'info');
- `app/static/js/organization/dashboard.js` L505: showMessage('User activity view functionality coming soon', 'info');
- `app/static/js/tools/soaps/soap_tool_events_exports.js` L340: SoapTool.ui.showSoapAlert('info', 'Recipe payload is ready. Push is stubbed for now; no data has been sent.', { dismissible: true, timeoutMs: 7000 });

## Scheduled vs unscheduled map
| Item | Scheduled now? | Where |
| --- | --- | --- |
| Service-boundary extraction (top offenders) | Yes | `docs/todo/LAUNCH_HARDENING_CHECKLIST.md` 4.2 |
| `role_required` removal/refactor | In progress | `docs/todo/LAUNCH_HARDENING_CHECKLIST.md` 4.3 (implementation done; callsite migration/deprecation remains) |
| Whop webhook/runtime stance | Yes | `docs/todo/LAUNCH_HARDENING_CHECKLIST.md` 5.1 and backlog launch blockers |
| POS module mock cleanup | Yes | `docs/todo/CONSOLIDATED_BACKLOG.md` (Bugs & Stability) |
| Developer waitlist placeholder route | Yes | `docs/todo/CONSOLIDATED_BACKLOG.md` (Bugs & Stability) |
| Fault-log placeholder surface | Yes | `docs/todo/CONSOLIDATED_BACKLOG.md` (Bugs & Stability) |
| Soap push stub workflow | Yes | `docs/todo/CONSOLIDATED_BACKLOG.md` (Future Features & Growth) |

## 10/10 target state (boundary-specific)
1. All non-public routes use permission decorators with zero audit violations.
2. Route modules are transport-only; service modules own business decisions; persistence access is encapsulated by service/repository modules.
3. Tenant scoping invariants are test-backed for all customer/org data paths; intentional global/developer exceptions are registry-documented.
4. Provider adapters are complete (or explicitly disabled via config guardrails), with no partial/stub runtime branches in production paths.
5. No explicit user-facing "coming soon" placeholders on operational/admin surfaces intended for launch use.

## Fix plan (implementation order, no calendar estimates)
### Workstream A: Permission integrity (high leverage, low blast radius)
- Continue migrating legacy role checks to canonical permission decorators and eventually deprecate `role_required`.
- Run route-permission audit in CI-friendly mode (with deterministic test DB config).

### Workstream B: Boundary extraction (high leverage, medium/high blast radius)
- Execute Priority 4.2 top-5 extraction list from hardening checklist first.
- For each file, move query/mutation blocks into service functions with explicit inputs/outputs and transaction ownership.
- Add focused integration tests around extracted service interfaces before deleting route-local logic.

### Workstream C: Integration hardening (medium leverage)
- Decide Whop launch posture: full support (webhook + checkout + cancellation + pricing) or hard disable with explicit UX + ops messaging.
- Move POS test stubs/mocks out of production file into tests fixtures.
- Implement Soap push backend endpoint + DTO validation + feature flag, or remove CTA path from UI until implemented.

### Workstream D: UI completion boundary (product polish with risk reduction)
- Replace operational/admin placeholders (`fault log`, `waitlist signups`) with real screens or remove routes from nav.
- Resolve customer-facing pending build notes where they conflict with launch readiness narratives.

## Appendix A: all controller/data-access offenders
- `app/blueprints/developer/system_roles.py`: 50
- `app/blueprints/developer/views/reference_routes.py`: 38
- `app/blueprints/developer/subscription_tiers.py`: 34
- `app/blueprints/organization/routes.py`: 33
- `app/blueprints/developer/views/global_item_routes.py`: 32
- `app/blueprints/auth/permissions.py`: 28
- `app/blueprints/conversion/routes.py`: 24
- `app/blueprints/inventory/routes.py`: 24
- `app/blueprints/auth/login_routes.py`: 19
- `app/blueprints/settings/routes.py`: 19
- `app/blueprints/products/product_variants.py`: 17
- `app/blueprints/batches/finish_batch.py`: 14
- `app/blueprints/expiration/services.py`: 14
- `app/blueprints/products/products.py`: 13
- `app/blueprints/products/product_inventory_routes.py`: 9 (resolved in this pass; removed from offender list)
- `app/blueprints/dashboard/routes.py`: 7 (resolved in this pass; removed from offender list)
- `app/blueprints/recipes/form_parsing.py`: 7 (resolved in this pass; removed from offender list)
- `app/blueprints/api/drawers/drawer_actions/global_link.py`: 6 (resolved in this pass; removed from offender list)
- `app/blueprints/products/sku.py`: 6 (resolved in this pass; removed from offender list)
- `app/blueprints/recipes/views/manage_routes.py`: 15 (resolved in this pass; removed from offender list)
- `app/blueprints/api/ingredient_routes.py`: 10 (resolved in this pass; removed from offender list)
- `app/blueprints/recipe_library/routes.py`: 6 (resolved in this pass; removed from offender list)
- `app/blueprints/recipes/views/create_routes.py`: 5 (resolved in this pass; removed from offender list)
- `app/blueprints/global_library/routes.py`: 4 (resolved in this pass; removed from offender list)
- `app/blueprints/api/drawers/drawer_actions/conversion_unit_mapping.py`: 3 (resolved in this pass; removed from offender list)
- `app/blueprints/api/drawers/drawer_actions/container_unit_mismatch.py`: 2 (resolved in this pass; removed from offender list)
- `app/blueprints/api/public.py`: 2 (resolved in this pass; removed from offender list)
- `app/blueprints/api/drawers/drawer_actions/retention.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/batches/start_batch.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/developer/views/dashboard_routes.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/developer/views/masquerade_routes.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/developer/views/organization_routes.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/expiration/routes.py`: 1 (resolved in this pass; removed from offender list)
- `app/blueprints/production_planning/routes.py`: 1 (resolved in this pass; removed from offender list)
