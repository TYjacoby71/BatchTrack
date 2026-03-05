# Billing System Source of Truth

## Synopsis
Billing is centralized in `BillingService` and is the authority for tier checkout, subscription state, and add-on activations.

## Glossary
- **Checkout session**: Provider-hosted flow for billing acceptance.
- **Webhook**: Provider callback that updates billing state.

## 1. Canonical Service
- **Provider authority**: `app/services/billing_service.py`
  - Handles Stripe initialization, price lookups, checkout sessions, webhook processing, customer portal sessions, subscription cancellations, and pending-signup provisioning.
- **Access-policy authority**: `app/services/billing_access_policy_service.py`
  - Produces canonical billing access decisions (`allow`, `require_upgrade`, `hard_lock`) for auth flows.
- **Workflow facades**: `app/services/billing/orchestrators/`
  - `AuthBillingOrchestrator` (auth/middleware)
  - `PublicSignupOrchestrator` (public signup routes)
  - `SettingsBillingOrchestrator` (settings billing context)
  - `AccountProvisioningOrchestrator` (post-checkout completion)
- All route handlers should orchestrate through these authorities and avoid direct provider branching in controllers.

## 2. Signup Flow (Stripe)
1. `/auth/signup` routes call `PublicSignupOrchestrator` (which delegates to `SignupCheckoutService`).
2. `SignupService.create_pending_signup_record` stores intent.
3. Stripe redirects user; webhook or `/billing/complete-signup-from-stripe` calls `BillingService._provision_checkout_session`.
4. `SignupService.complete_pending_signup_from_checkout` creates the org + owner, emits events, and logs the owner in.

### 2.0 Free-priced Stripe tiers
- If live Stripe amount for a signup tier resolves to `0`, signup payload labels the tier `FREE`.
- Stripe checkout skips free-trial injection for zero-priced subscriptions.
- Stripe checkout sets `payment_method_collection=if_required` for zero-priced subscriptions and provides user copy that card entry is optional and can be added later in settings.

### 2.1 Lifetime launch mode (coupon + seat counters)
- Signup now supports `billing_mode=lifetime` with three launch tiers:
  - Hobbyist (`2000` seats, display floor `1997`)
  - Enthusiast (`1000` seats, display floor `995`)
  - Fanatic (`500` seats, display floor `492`)
- When all lifetime seats are sold out, signup automatically defaults to:
  - `billing_mode=standard`
  - `billing_cycle=yearly`
  while still allowing users to toggle monthly/yearly.
- Seat counters are promo-code based (`organization.promo_code`), with floor logic:
  - Show the floor value while sold count is below `total - floor`.
  - Show true remaining once sold count reaches the threshold.
- Lifetime checkout uses the tier's single configured Stripe lookup key and derives related keys by naming convention:
  - standard monthly: `<tier>_monthly` (stored in `subscription_tier.stripe_lookup_key`)
  - standard yearly: `<tier>_yearly`
  - lifetime one-time: `<tier>_lifetime`

### 2.2 Stripe production structure (single-key tier model)
This app intentionally stores **one** Stripe lookup key per tier in the database.

#### Required Stripe setup per tier
For each paid tier (for example Hobbyist, Enthusiast, Fanatic, Enterprise):
1. Create one Stripe Product (for grouping and dashboard clarity).
2. Create three Stripe Prices under that product with lookup keys:
   - `<slug>_monthly` (recurring monthly)
   - `<slug>_yearly` (recurring yearly)
   - `<slug>_lifetime` (one-time payment)
3. In BatchTrack tier admin, set only:
   - `billing_provider = stripe`
   - `stripe_lookup_key = <slug>_monthly`

#### How checkout key selection works
- Standard monthly: uses stored `stripe_lookup_key` directly.
- Standard yearly: derives `<slug>_yearly` from the stored monthly key.
- Lifetime: derives `<slug>_lifetime` from the stored monthly key and requires one-time Stripe billing cycle.

If derived yearly/lifetime keys do not exist (or lifecycle type is wrong), signup falls back with an error message instead of creating an invalid checkout session.

### 2.3 Lifetime counter behavior and price changes
- Counter source of truth: `organization.promo_code` values in app DB (not Stripe price IDs).
- Default coupon buckets:
  - `LIFETIME-HOBBYIST`
  - `LIFETIME-ENTHUSIAST`
  - `LIFETIME-FANATIC`
- Replacing a Stripe lifetime price does **not** break existing counts if you keep the same lifetime coupon code bucket for that tier.
- Existing paid users on older Stripe prices continue to work as long as billing status stays active.

### 2.4 Updating prices safely
Two valid operating styles:
1. **Stable lookup keys (recommended)**  
   Keep keys unchanged (for example `hobbyist_monthly`) and point the key to the newest Stripe price.
2. **Versioned lookup keys**  
   If you use `_v2`, `_v3`, etc., update the entire family (`monthly/yearly/lifetime`) together.  
   Updating only monthly to `..._v2` while yearly/lifetime remain `..._v1` will make derived yearly/lifetime lookups unavailable.

### 2.5 Tiers beyond the original three
Tier names are not hardcoded to Hobbyist/Enthusiast/Fanatic for standard monthly/yearly billing.
- Any new tier (for example Enterprise) works with the same naming pattern:
  - `enterprise_monthly`
  - `enterprise_yearly`
  - `enterprise_lifetime` (if offered)
- Lifetime launch seat-counter UX is currently designed around the three launch buckets above.

## 3. Webhooks & Callbacks
- **Endpoint**: `POST /billing/webhooks/stripe`
- `BillingService.handle_webhook_event('stripe', payload)` enforces idempotency via `stripe_event` table.
- Subscription events update org billing status and add-ons.
- Checkout success reuses `_provision_checkout_session`.
- Current Whop webhook handler is present as a placeholder branch in `BillingService.handle_webhook_event` but full provider lifecycle parity is not yet implemented.

## 4. Add-ons & Entitlements
- Add-on structure and entitlement logic lives in [ADDONS_AND_ENTITLEMENTS.md](ADDONS_AND_ENTITLEMENTS.md).
- Add-ons are activated by Stripe webhook events that map price lookup keys to catalog add-ons.
- Tier editing and add-on availability are managed under `/developer/subscription-tiers` and `/developer/addons`.

## 5. Environment Requirements
- Secrets pulled from env vars (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, etc.). Production refuses to boot without Redis-backed cache, sessions, and rate limiting.
- No config-file fallbacks for billing credentials; missing env vars cause immediate failure when `BillingService.ensure_stripe()` is called.

## 6. Testing Strategy
- Primary test: `tests/test_signup_stripe_flow.py::test_signup_flow_end_to_end`
  - Default: Monkeypatched Stripe, verifies entire signup + callback logic.
  - Live mode: `pytest --stripe-live` uses real env keys, creates authentic checkout sessions, and expects webhooks to finish provisioning.
- Do **not** introduce additional Stripe test helpers; extend this test if new behavior must be validated.

## 7. Change Process
1. Update `BillingService` for provider behavior changes (checkout/webhooks/customer portal/cancellation).
2. Update `BillingAccessPolicyService` for billing access semantics (recoverable vs lockout states).
3. Keep middleware transport-only (`app/middleware/guards.py` + `app/middleware/registry.py`); do not re-embed policy branching there.
4. Keep auth/login gating aligned by using `AuthBillingOrchestrator`.
5. Document behavior changes here and in `docs/system/SERVICES.md`.
6. If new providers are added, route through `BillingService` and then expose workflow entrypoints through billing orchestrators.

## 8. Billing Access Policy Boundary
- **Policy authority:** `BillingAccessPolicyService.evaluate_organization(organization)`
  - Returns a structured decision:
    - `allow` (no billing redirect/block)
    - `require_upgrade` (recoverable billing state such as `payment_failed`/`past_due`)
    - `hard_lock` (organization explicitly inactive, or non-exempt tier in suspended/canceled states)
  - Billing-exempt tiers (`billing_provider = exempt`) bypass subscription/payment-status gating.
- **Request enforcement:** `app/middleware/guards.py::enforce_billing` (wired via `app/middleware/registry.py`)
  - Applies transport behavior only (redirect, JSON error, logout/session invalidation).
  - Must not duplicate business-policy branching that belongs to the policy service.
- **Auth login enforcement:** `app/blueprints/auth/login_routes.py`
  - Uses the same policy service to deny login on `hard_lock` decisions so stale sessions cannot re-enter protected pages.

## 9. Destructive Deletion Billing Safety
- `OrganizationService.delete_organization` cancels Stripe subscription first when `stripe_customer_id` exists; deletion aborts if cancellation fails.
- `UserService.hard_delete_user` cancels Stripe subscription first when deleting the final non-deleted customer account in an organization; hard delete aborts if cancellation fails.
- This prevents orphan subscriptions during destructive account cleanup.

This document supersedes any legacy references to `StripeService` and monolithic middleware billing gates. All future fixes should update this file to keep billing architecture coherent.
