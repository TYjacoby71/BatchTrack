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
- [ ] Add password strength check (min 8 chars) to signup route (`app/blueprints/auth/login_routes.py` or signup handler)
- [ ] Add password strength check to quick-signup route (`app/blueprints/auth/login_routes.py`)
- [ ] Add password strength check to invite/user-creation flow (`app/services/user_invite_service.py`)
- [ ] Add password strength check to password change route (`app/blueprints/settings/routes.py`)
- [ ] Verify password reset route already has the check (`app/blueprints/auth/password_routes.py` line 150 — confirmed)
- [ ] Add tests for password validation rejection

### 1.4 Login lockout mechanism
- [ ] Add failed-login attempt tracking (counter per username or IP, stored in Redis or DB)
- [ ] Lock account or add CAPTCHA after N failed attempts (recommend 5 within 15 minutes)
- [ ] Add unlock mechanism (time-based auto-unlock after 30 minutes, or admin manual unlock)
- [ ] Add tests for lockout behavior

### 1.5 Public signup commerce hardening
- [ ] Add billing-consent microcopy near the signup CTA with Terms + Privacy links and recurring billing language (`app/templates/pages/auth/signup.html`)
- [ ] Make the 14-day trial explicit in checkout session construction (`app/services/billing_service.py`) by setting subscription trial parameters in code, or documenting the enforced Stripe-level equivalent
- [ ] Configure explicit tax behavior for checkout (`app/services/billing_service.py`) including `automatic_tax` and tax-ID collection policy
- [ ] Replace legal placeholders before launch (`app/templates/legal/terms_of_service.html`, `app/templates/legal/privacy_policy.html`) including governing jurisdiction and business address
- [ ] Tighten public signup abuse controls (`app/blueprints/auth/signup_routes.py`) with stricter throttles and bot challenge strategy at threshold
- [ ] Add a no-JavaScript fallback submit path for checkout handoff (`app/templates/pages/auth/signup.html`) so payment flow still works when scripts are blocked

---

## Priority 2: Production Visibility

### 2.1 Add logging to silent exception handlers
- [ ] `app/template_context.py` (12 silent handlers): add `logger.debug()` or `logger.warning()` to each
- [ ] `app/services/batch_service/batch_operations.py` (~20 silent handlers): add logging
- [ ] `app/services/recipe_service/_core.py` (~15 silent handlers): add logging
- [ ] `app/middleware.py` (~10 silent handlers): add logging
- [ ] `app/blueprints/tools/routes.py` (7 silent handlers): add logging
- [ ] `app/blueprints/inventory/routes.py` (5 silent handlers): add logging
- [ ] Remaining files: search for `except Exception` and `except:` without a `logger.` call on the next line; fix all remaining instances
- [ ] Verify no bare `except:` clauses remain (currently 1 in `cache_manager.py`)

### 2.2 Replace pickle in cache manager
- [ ] `app/utils/cache_manager.py` line 161: replace `pickle.loads(raw)` with JSON deserialization
- [ ] Replace corresponding `pickle.dumps()` with JSON serialization
- [ ] Add test to verify cache serialization round-trips correctly

### 2.3 Branded error pages
- [ ] Create `app/templates/errors/404.html` (not found)
- [ ] Create `app/templates/errors/500.html` (server error)
- [ ] Register Flask error handlers in `app/resilience.py` for 404 and 500
- [ ] Verify `errors/maintenance.html` (503) is already registered (confirmed)

---

## Priority 3: Test Coverage for Critical Paths

### 3.1 Auth flow tests
- [ ] Login success and failure (username/password)
- [ ] Signup flow (form validation, org creation, tier assignment)
- [ ] Password reset request and completion
- [ ] Email verification flow
- [ ] OAuth callback handling (Google flow beyond current coverage)
- [ ] Session enforcement (single-session guard)

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
- [ ] `app/blueprints/developer/views/reference_routes.py` (11 violations): extract DB operations into a developer reference service
- [ ] `app/blueprints/products/product_variants.py` (9 violations): move DB operations into `product_service.py`
- [ ] `app/blueprints/settings/routes.py` (9 violations): extract into a settings service
- [ ] `app/blueprints/inventory/routes.py` (8 violations): move remaining DB operations into `inventory_adjustment` service
- [ ] `app/blueprints/organization/routes.py` (8 violations): extract into an organization service

### 4.3 God file refactoring
- [ ] `app/services/billing_service.py` (1,612 lines): split into billing_checkout, billing_webhook, billing_query modules
- [ ] `app/services/recipe_service/_core.py` (1,454 lines): already has helpers; evaluate if more can be extracted
- [ ] `app/blueprints/inventory/routes.py` (1,368 lines): split into inventory_views, inventory_api, inventory_actions
- [ ] `app/services/batch_service/batch_operations.py` (1,239 lines): split start/finish/cancel into separate modules
- [ ] `app/services/public_bot_trap_service.py` (1,148 lines): split policy logic from hit recording
- [ ] `app/utils/permissions.py` (1,085 lines): split permission checking from role/hierarchy utilities

---

## How to Use This Checklist

Pick the next unchecked box. Complete it. Check it off. Commit. Move to the next one.

Each box is scoped to be completable in one session. Boxes within a section can be done in any order. Sections should be done in priority order.

Run `make lint` and `make test` after each section to verify nothing broke.
