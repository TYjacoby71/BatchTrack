## Summary
Implemented end-to-end PostHog funnel instrumentation across public, auth, onboarding, and core in-app workflows, then remediated Documentation Guard requirements for touched files.

## Problems Solved
- Core activation timing was not consistently queryable for first/second use of key actions.
- Backend domain events were not automatically forwarded to PostHog capture as a server-side sink.
- Signup-to-checkout timing lacked a durable first-landing timestamp bridge.
- PR checks failed due documentation-guard schema requirements on touched Python modules and missing APP_DICTIONARY path coverage.

## Key Changes
- Added backend event enrichment for core events:
  - `user_use_index`, `org_use_index`
  - `is_first_user_use`, `is_second_user_use`
  - `seconds_since_first_login`
- Added and/or enriched key events for activation and funnel analysis:
  - `inventory_item_custom_created`, `inventory_item_global_created`, `inventory_item_created`
  - `recipe_variation_created`, `recipe_test_created`
  - `plan_production_requested`, `stock_check_run`
  - `user_login_succeeded`, `signup_checkout_started`, `signup_checkout_completed`, `purchase_completed`, `onboarding_completed`
- Added first-landing timing plumbing:
  - New helper `app/utils/analytics_timing.py`
  - Client-side first-landing capture persisted in localStorage/cookie
  - Signup form forwarding of `client_first_landing_at` and server-side elapsed-seconds enrichment
- Extended outbox dispatcher delivery support to PostHog capture API while preserving webhook delivery behavior.
- Updated tracking/system documentation and corrected documentation-guard schema items (module synopsis/glossary + functional unit headers + dictionary coverage).

## Files Modified
- `app/services/event_emitter.py`
- `app/services/domain_event_dispatcher.py`
- `app/services/inventory_adjustment/_creation_logic.py`
- `app/services/recipe_service/_core.py`
- `app/blueprints/production_planning/routes.py`
- `app/blueprints/auth/login_routes.py`
- `app/blueprints/auth/oauth_routes.py`
- `app/blueprints/onboarding/routes.py`
- `app/blueprints/billing/routes.py`
- `app/services/signup_checkout_service.py`
- `app/services/signup_service.py`
- `app/utils/analytics_timing.py`
- `app/templates/layout.html`
- `app/templates/homepage.html`
- `app/templates/pages/auth/login.html`
- `app/templates/pages/auth/signup.html`
- `app/templates/pages/public/pricing.html`
- `app/templates/pages/public/landing_hormozi.html`
- `app/templates/pages/public/landing_robbins.html`
- `app/templates/onboarding/welcome.html`
- `docs/system/TRACKING_PLAN.md`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
