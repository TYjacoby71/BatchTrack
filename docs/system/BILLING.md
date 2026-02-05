# Billing System Source of Truth

## Synopsis
Billing is centralized in `BillingService` and is the authority for tier checkout, subscription state, and add-on activations.

## 1. Canonical Service
- **Authority**: `app/services/billing_service.py`
- Handles Stripe initialization, price lookups, checkout sessions, webhook processing, customer portal sessions, subscription cancellations, and pending-signup provisioning.
- All routes/services must call this module; no direct Stripe SDK usage elsewhere.

## 2. Signup Flow (Stripe)
1. `/auth/signup` (POST) calls `BillingService.create_checkout_session_for_tier`.
2. `SignupService.create_pending_signup_record` stores intent.
3. Stripe redirects user; webhook or `/billing/complete-signup-from-stripe` calls `BillingService._provision_checkout_session`.
4. `SignupService.complete_pending_signup_from_checkout` creates the org + owner, emits events, and logs the owner in.

## 3. Webhooks & Callbacks
- **Endpoint**: `POST /billing/webhooks/stripe`
- `BillingService.handle_webhook_event('stripe', payload)` enforces idempotency via `stripe_event` table.
- Subscription events update org billing status and add-ons.
- Checkout success reuses `_provision_checkout_session`.
- Future providers (Whop, etc.) must plug into `BillingService.handle_webhook_event`.

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
1. Update `BillingService` (never reintroduce parallel services).
2. Document behavior changes here and in `docs/system/SERVICES.md`.
3. Expand `test_signup_flow_end_to_end` instead of creating new ad-hoc tests.
4. If new providers are added, they must be routed through `BillingService`.

This document supersedes any legacy references to `StripeService`. All future fixes must consult and update this file to keep the billing architecture coherent.***
