## Summary
Introduced a centralized analytics registry + relay service, then refactored funnel and activation emitters to use thin service calls instead of direct, repeated `EventEmitter.emit(...)` blocks.

## Problems Solved
- Analytics event contracts (names/required fields/core-usage classification) were spread across multiple files.
- Feature modules contained repeated verbose emitter boilerplate, making payload consistency harder to maintain.
- It was difficult to quickly discover canonical events and required properties in one place.

## Key Changes
- Added canonical analytics registry:
  - `app/services/analytics_event_registry.py`
  - Includes event specs, required property metadata, and `CORE_USAGE_EVENT_NAMES`.
- Added centralized analytics relay:
  - `app/services/analytics_tracking_service.py`
  - Validates required properties, normalizes code-usage fields, and delegates to `EventEmitter`.
- Updated `EventEmitter` core usage configuration to source from registry:
  - `EventEmitter._CORE_USAGE_EVENTS = set(CORE_USAGE_EVENT_NAMES)`
- Refactored high-volume funnel and activation emitters to use relay calls:
  - auth login/quick-signup/dev-login
  - OAuth login success
  - billing checkout-start and signup-checkout login success
  - onboarding completion
  - signup checkout start
  - signup completion + purchase bundle emission
  - inventory creation source events
  - recipe create/update/delete event emission
  - production planning + stock-check events
  - batch lifecycle events
  - timer started/stopped events
- Updated tracking documentation and dictionary entries to document the registry/relay architecture.

## Files Modified
- `app/services/analytics_event_registry.py` (new)
- `app/services/analytics_tracking_service.py` (new)
- `app/services/event_emitter.py`
- `app/blueprints/auth/login_routes.py`
- `app/blueprints/auth/oauth_routes.py`
- `app/blueprints/billing/routes.py`
- `app/blueprints/onboarding/routes.py`
- `app/services/signup_checkout_service.py`
- `app/services/signup_service.py`
- `app/services/inventory_adjustment/_creation_logic.py`
- `app/services/recipe_service/_core.py`
- `app/blueprints/production_planning/routes.py`
- `app/services/batch_service/batch_operations.py`
- `app/services/timer_service.py`
- `docs/system/TRACKING_PLAN.md`
- `docs/system/APP_DICTIONARY.md`
