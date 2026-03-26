# Launch Hardening Checklist

## Synopsis
Ordered checklist of fixes required before BatchTrack can safely serve real customer data. Items are ranked by risk and sequenced so each can be completed independently. Work top to bottom.

## Glossary
- **Scoped query**: A query filtered by `organization_id` to enforce tenant isolation.
- **Service boundary**: The rule that blueprints call services for business logic instead of touching `db.session` directly.

---

## Priority 1: Launch Blockers

### 1.1 Clean requirements.txt
- [x] Remove duplicate entries (`Flask-WTF`, `flask-mail`/`Flask-Mail`, `Flask-Limiter`, `Flask-Migrate`, `redis`, `openai`, `xlrd`)
- [x] Pin all 34 unpinned packages to current installed versions
- [x] Remove conflicting version specs (`redis>=5.0.0` vs `redis==5.1.1`, `Flask-WTF>=1.1.0` vs `Flask-WTF==1.2.1`)
- [x] Verify clean install: `pip install -r requirements.txt` on a fresh venv with zero warnings

### 1.2 Audit and fix unscoped queries
- [x] Inventory blueprint (`app/blueprints/inventory/routes.py`): 10 queries scoped
- [x] Products blueprint (`products.py`, `sku.py`, `product_variants.py`, `product_inventory_routes.py`, `reservation_routes.py`): 67 queries scoped
- [x] Recipes blueprint (`manage_routes.py`, `lineage_routes.py`, `create_routes.py`, `ajax_routes.py`, `form_templates.py`, `form_parsing.py`, `form_prefill.py`, `form_variations.py`): 24 queries scoped
- [x] Batches blueprint (`finish_batch.py`): 12 queries scoped
- [x] Timers blueprint (`routes.py`): 3 queries scoped
- [x] Conversion blueprint (`routes.py`): 8 queries scoped
- [x] Organization blueprint (`routes.py`): 4 Role queries scoped
- [x] API blueprints (`fifo_routes.py`, `routes.py`, `ingredient_routes.py`, `reservation_routes.py`, drawers): 18 queries scoped
- [x] Expiration blueprint (`routes.py`, `services.py`): 11 queries scoped
- [x] Production planning blueprint (`routes.py`): 4 queries scoped
- [x] Dashboard blueprint (`routes.py`): 1 query scoped
- [x] Developer/admin blueprints: verified — intentionally unscoped with developer-only access guards
- [x] Recipe library blueprint: verified — intentionally unscoped (public recipe library)
- [x] Auth blueprint: verified — `Role.query` for system role lookup is safe (not tenant data)
- [x] Final pass: 171 queries fixed across 31 files; only intentional exceptions remain (recipe library, auth system roles, global library with manual org_id filter)

### 1.3 Server-side password validation
- [x] Add password strength check (min 8 chars) to signup route (`app/services/signup_checkout_service.py` validates optional submitted password length)
- [x] Add password strength check to quick-signup route (`app/blueprints/auth/login_routes.py`)
- [x] Add password strength check to invite/user-creation flow (`app/services/user_invite_service.py` now issues invite setup path where password creation enforces min 8 in `app/blueprints/onboarding/routes.py`)
- [x] Add password strength check to password change route (`app/blueprints/settings/routes.py`)
- [x] Verify password reset route already has the check (`app/blueprints/auth/password_routes.py` line 150 — confirmed)
- [x] Add tests for password validation rejection

### 1.4 Login lockout mechanism
- [x] Add failed-login attempt tracking (counter per user identifier via cache-backed lockout state)
- [x] Lock account after N failed attempts (configured at 10 within 15 minutes per user identifier)
- [x] Add unlock mechanism (password reset flow via existing forgot/reset routes)
- [x] Add tests for lockout behavior

### 1.5 Public signup commerce hardening
- [x] Add billing-consent microcopy near the signup CTA with Terms + Privacy links and recurring billing language (`app/templates/pages/auth/signup.html`)
- [x] Make the 14-day trial explicit in checkout session construction (`app/services/billing_service.py`) by setting `subscription_data.trial_period_days` via `create_checkout_session_for_tier`
- [x] Configure explicit tax behavior for checkout (`app/services/billing_service.py`) including `automatic_tax` and tax-ID collection policy (`SIGNUP_STRIPE_AUTOMATIC_TAX_ENABLED`, `SIGNUP_STRIPE_TAX_ID_COLLECTION_ENABLED`)
- [x] Replace legal placeholders before launch (`app/templates/legal/terms_of_service.html`, `app/templates/legal/privacy_policy.html`, `app/templates/legal/cookie_policy.html`) including governing jurisdiction and business/address copy (BatchTrack.com cloud business profile + no public mailing address)
- [ ] Finalize enforceable legal metadata in Terms/Privacy (`app/templates/legal/terms_of_service.html`, `app/templates/legal/privacy_policy.html`): explicit governing jurisdiction + venue, formal registered legal entity name, and legal notice contact policy
- [ ] Tighten public signup abuse controls (`app/blueprints/auth/signup_routes.py`) with stricter throttles and bot challenge strategy at threshold
- [ ] Add a no-JavaScript fallback submit path for checkout handoff (`app/templates/pages/auth/signup.html`) so payment flow still works when scripts are blocked

---

## Priority 2: Production Visibility

### 2.1 Add logging to silent exception handlers
- [x] `app/template_context.py` (12 silent handlers): add `logger.debug()` or `logger.warning()` to each
- [x] `app/services/batch_service/batch_operations.py` (~20 silent handlers): add logging
- [x] `app/services/recipe_service/_core.py` (~15 silent handlers): add logging
- [x] `app/middleware.py` (~10 silent handlers): add logging
- [x] `app/blueprints/tools/routes.py` (7 silent handlers): add logging
- [x] `app/blueprints/inventory/routes.py` (5 silent handlers): add logging
- [x] Remaining files: search for `except Exception` and `except:` without a `logger.` call on the next line; fix all remaining instances
- [x] Verify no bare `except:` clauses remain (confirmed)

### 2.2 Replace pickle in cache manager
- [x] `app/utils/cache_manager.py` line 161: replace `pickle.loads(raw)` with JSON deserialization
- [x] Replace corresponding `pickle.dumps()` with JSON serialization
- [x] Add test to verify cache serialization round-trips correctly

### 2.3 Branded error pages
- [x] Create `app/templates/errors/404.html` (not found)
- [x] Create `app/templates/errors/500.html` (server error)
- [x] Register Flask error handlers in `app/resilience.py` for 404 and 500
- [x] Verify `errors/maintenance.html` (503) is already registered (confirmed)

### 2.4 Request correlation and access-log schema parity
- [x] Generate or preserve `X-Request-ID` in middleware and include it on all responses
- [x] Add `request_id` to application log output format via logging filter context
- [x] Include request ID and `X-Forwarded-For` in Gunicorn access logs for edge/origin joins
- [x] Add focused middleware tests to verify request-ID propagation and passthrough behavior

---

## Priority 3: Test Coverage for Critical Paths

### 3.1 Auth flow tests
- [x] Login success and failure (username/password)
- [x] Signup flow (form validation, org creation, tier assignment)
- [ ] Password reset request and completion (deferred in current scope by request)
- [x] Email verification flow
- [x] OAuth callback handling (Google flow beyond current coverage)
- [x] Session enforcement (single-session guard)

### 3.2 Organization management tests
- [ ] Invite user flow (create user, assign role, email dispatch)
- [ ] Role creation and permission assignment
- [ ] User deactivation and reactivation
- [ ] Tier enforcement on user limits

### 3.3 Billing flow tests
- [ ] Checkout session creation for each tier
- [ ] Webhook handling (subscription created, updated, deleted)
- [ ] Billing access policy enforcement (hard lock, require upgrade, allow)
- [ ] Add-on activation via webhook

### 3.4 Settings and profile tests
- [ ] Password change
- [ ] Timezone update
- [ ] User preference persistence
- [ ] System settings update (developer only)

---

## Priority 4: Structural Cleanup

### 4.1 Lint baseline to zero
- [ ] Run `ruff check --fix app/ tests/` to auto-fix 3 unused imports
- [ ] Run `black app/ tests/` to format 40 files
- [ ] Run `isort app/ tests/` to fix 4 import ordering issues
- [ ] Verify `make lint` passes clean

### 4.2 Service boundary enforcement (top 5 offenders)
- [x] `app/blueprints/developer/views/reference_routes.py` (11 violations): extract DB operations into a developer reference service
- [x] `app/blueprints/products/product_variants.py` (9 violations): move DB operations into `product_service.py`
- [x] `app/blueprints/settings/routes.py` (9 violations): extract into a settings service
- [x] `app/blueprints/inventory/routes.py` (8 violations): move remaining DB operations into `inventory_adjustment` service
- [x] `app/blueprints/organization/routes.py` (8 violations): extract into an organization service

### 4.3 God file refactoring
- [ ] `app/services/billing_service.py` (1,612 lines): split into billing_checkout, billing_webhook, billing_query modules
- [ ] `app/services/recipe_service/_core.py` (1,454 lines): already has helpers; evaluate if more can be extracted
- [ ] `app/blueprints/inventory/routes.py` (1,368 lines): split into inventory_views, inventory_api, inventory_actions
- [ ] `app/services/batch_service/batch_operations.py` (1,239 lines): split start/finish/cancel into separate modules
- [ ] `app/services/public_bot_trap_service.py` (1,148 lines): split policy logic from hit recording
- [ ] `app/utils/permissions.py` (1,085 lines): split permission checking from role/hierarchy utilities
  - [ ] Create package scaffold `app/utils/permissions/` and keep `app/utils/permissions.py` as a temporary compatibility entrypoint
  - [ ] Move decorators and denied-response HTTP behavior to `app/utils/permissions/decorators.py` (`require_permission`, `any_permission_required`, denied response builders)
  - [ ] Move request/org context helpers to `app/utils/permissions/context.py` (`get_effective_organization_id`, `get_effective_organization`, owner/developer context helpers)
  - [ ] Move permission-scope/catalog resolution + cache helpers to `app/utils/permissions/catalog.py` (`PermissionScope`, `resolve_permission_scope`, cache clear helpers)
  - [ ] Move authorization engine to `app/utils/permissions/authorization.py` (`AuthorizationHierarchy` and tier/add-on permission composition)
  - [ ] Move feature gating helpers to `app/utils/permissions/feature_gate.py` (`FeatureGate`)
  - [ ] Move legacy wrappers/shims to `app/utils/permissions/legacy.py` (`require_permission_with_org_scoping`, `require_system_admin`, etc.)
  - [ ] Add `app/utils/permissions/__init__.py` exports that preserve all current import names during migration
  - [ ] Migrate imports incrementally across blueprints/services to module-specific imports after compatibility exports are in place
  - [ ] Remove stub/unused paths (`role_required` TODO path, deprecated enum/wrappers not used by callsites) only after import migration + parity verification

---

## Priority 5: SaaS Operational Maturity (Next Phase)

### 5.1 Billing reliability and replay safety
- [ ] Add outbound Stripe idempotency keys for mutating API calls (checkout/session creation, customer metadata writes, cancellations)
- [ ] Enforce webhook environment/shape checks (`livemode`, provider version expectations) before applying state transitions
- [ ] Add Stripe webhook replay tooling for failed events (developer command + safe status transition from `failed` to `received`)
- [ ] Add dead-letter visibility for webhook processing failures (dashboard count + alert threshold)
- [ ] Add retention/pruning policy for `stripe_event` table to prevent unbounded growth
- [ ] Implement Whop webhook handler path or explicitly disable and document non-support in runtime checks

### 5.2 Async side effects and queue durability
- [ ] Introduce a background job worker for non-critical request side effects (emails, outbound webhooks, analytics fan-out)
- [ ] Move signup completion email fan-out off the request path (verification, welcome, password setup)
- [ ] Add retry policy with exponential backoff and dead-letter handling for failed jobs
- [ ] Ensure domain-event dispatcher failures are observable with explicit queue backlog metrics and alerting
- [ ] Add runbook for replaying domain events that exceeded retry threshold

### 5.3 Public edge abuse, throttling, and cost controls
- [ ] Reclassify rate limits by endpoint risk class (auth, public compute, webhook, read-only public search)
- [ ] Remove/justify limiter exemptions on public compute endpoints and add explicit per-IP caps
- [ ] Tighten signup/login throttles to production-safe defaults and document override policy for controlled load tests
- [ ] Add abuse telemetry dashboards for 403/429 rates, bot-trap actions, and high-cost endpoint traffic spikes
- [ ] Add webhook endpoint abuse protections (source validation + saturation-safe limits)

### 5.4 Access governance and policy drift prevention
- [ ] Replace static route allowlists with decorator/registry-driven route classification for public/developer/customer access
- [ ] Add CI guard that fails when new routes are introduced without access classification metadata
- [ ] Add scheduled access-audit report for publicly reachable endpoints and developer-only endpoints
- [ ] Add policy regression tests for route classification drift

### 5.5 Data model and state-machine hygiene
- [ ] Clean legacy/duplicate billing fields from `Organization` and document canonical fields
- [ ] Add explicit allowed-state transitions for billing/subscription statuses to avoid invalid state writes
- [ ] Add migration guardrails for high-risk model changes (backfill + verification query + rollback notes)
- [ ] Add periodic data-integrity checks for billing/customer linkage consistency

### 5.6 Observability, incident response, and recovery
- [ ] Add production error monitoring (e.g., Sentry/OpenTelemetry) with request ID tags on all errors
- [ ] Propagate request correlation ID into domain events (`correlation_id`) for cross-log/event tracing
- [ ] Define SLOs + alert thresholds for login success, signup completion, checkout conversion, and webhook lag
- [ ] Add structured incident runbook for billing/webhook failures (detect, triage, replay, verify, closeout)
- [ ] Replace auto-backup toggle stub with real scheduled backup + restore workflow
- [ ] Run and document periodic restore drills (RPO/RTO targets + evidence)

### 5.7 Managed WAF migration (if adopted)
- [x] Select edge WAF provider and define ownership, failure policy (fail-open/fail-closed), and rollback runbook
- [x] Confirm ownership model: domain registrar (e.g., GoDaddy) is not the WAF; WAF is managed in a separate edge account
- [x] Select and fund the required WAF tier (managed rules, bot management, and rate limiting may require paid plans)
  - Current state: Cloudflare Free tier selected; reevaluate upgrade if managed rules/rate controls are needed.
- [x] Decide DNS onboarding path for edge protection (move authoritative DNS to edge provider or use provider-supported partial/CNAME setup)
- [x] Run WAF in observe/log-only mode and compare outcomes with current bot-trap/security decisions before enforcement
- [ ] Enable managed exploit signatures (OWASP/Cloudflare managed rules) for recurring probes (`/xmlrpc.php`, WordPress paths, random `*.php` scans)
  - Pending tier upgrade from Free plan.
- [x] Add custom edge rules for recurring probes (`/xmlrpc.php`, WordPress paths, random `*.php` scans)
- [ ] Add verified-bot policy for search/ad/social crawlers using provider verification (reverse DNS/IP ranges), not user-agent string alone
- [x] Add behavior-based controls for scanner patterns (bursting, high 404/403 ratios, high path entropy, HEAD sweeps across unknown paths)
  - Implemented: custom probe-block rule and auth path rate-limit rule (Free-tier constraints applied).
- [ ] Add challenge-first policy for medium-confidence traffic and block-only for high-confidence abuse
- [ ] Lock origin to edge-only ingress (reject direct-to-origin internet traffic)
- [x] Enable origin-auth handshake between edge and app (`ENFORCE_EDGE_ORIGIN_AUTH`, `EDGE_ORIGIN_AUTH_HEADER`, `EDGE_ORIGIN_AUTH_SECRET`) after shadow validation
- [ ] Re-scope `/api/public/bot-trap` to telemetry-only (or remove) once equivalent WAF controls are enforced
- [ ] Add WAF dashboards and alerts (block/challenge rates, top rules, top source ASNs/IPs, false-positive samples)
- [ ] Roll out in phases (shadow -> challenge -> block) with explicit conversion guardrails on `/homepage`, `/help/how-it-works`, `/signup`, and `/auth/signup`

---

## How to Use This Checklist

Pick the next unchecked box. Complete it. Check it off. Commit. Move to the next one.

Each box is scoped to be completable in one session. Boxes within a section can be done in any order. Sections should be done in priority order.

Run `make lint` and `make test` after each section to verify nothing broke.
