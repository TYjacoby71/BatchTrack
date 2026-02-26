# Stripe Integration

## Synopsis
How BatchTrack integrates with Stripe for subscription billing: checkout session construction, price resolution, webhook handling, and common failure modes.

## Glossary
- **Lookup key**: Stripe price identifier stored on `SubscriptionTier.stripe_lookup_key`.
- **Checkout session**: Stripe-hosted payment form created by `BillingService`.

This document is the point of truth for how BatchTrack integrates with Stripe. Use it before touching billing code so fixes stay consistent.

## High-Level Flow

1. **Signup form** (`/auth/signup`) collects tier choice and optional referral / OAuth data.
2. **`BillingService.create_checkout_session_for_tier`** is called with the chosen tier and whatever customer info we already have (OAuth email, etc.).
3. The service fetches live pricing for the tier, builds a Checkout Session payload, and redirects the browser to Stripe Checkout.
4. Stripe hosts the payment form, collecting card details and any missing customer fields.
5. Stripe redirects back to `/billing/complete-signup-from-stripe` with `session_id`.
6. Webhooks (`/billing/webhooks/stripe`) finalize subscription state, update org records, and enable add-ons.

## Price Resolution Rules

Tiers store a `stripe_lookup_key`. Stripe best practice is to set this equal to the Price’s lookup key. In production we have a mix of true lookup keys and raw `price_*` IDs, so the service resolves prices with a two-step strategy:

1. Attempt `stripe.Price.list(lookup_keys=[key])`.
2. If no match, treat the value as a direct `price_*` ID via `stripe.Price.retrieve`.

Results are cached in-process for 10 minutes to cut down on API calls. Make sure any new tier gets a real lookup key in Stripe. If you must use a raw price ID, understand that you lose the ability to rotate underlying prices without touching the DB.

## Checkout Session Construction

Key behaviors in `BillingService.create_checkout_session_for_tier`:

- Always request `mode='subscription'` with the single resolved price.
- Metadata automatically includes `tier_id`, `tier_name`, and the stored lookup key; caller metadata is merged in.
- If we already know the email (OAuth signups), we set `customer_email`. Otherwise Stripe is asked to create the customer (`customer_creation='always'`) so there is no invalid `customer_update` payload.
- Optional `client_reference_id` lets controllers correlate pending signup rows with Stripe sessions.
- `session_overrides` allow experiments, but any `customer_update` block is stripped unless a fixed `customer` is supplied. This prevents the `customer_update can only be used with customer` 500s seen in logs.

### Passing Customer Data

The signup form currently does **not** collect email/password up front for card-based signups. Instead we rely on Stripe Checkout to gather contact info. Only OAuth signups pass an email during session creation. If you need customer-scoped features (e.g., `customer_update`, saved payment methods), you must either:

1. Collect the email on our form and pass it as `customer_email`, or
2. Pre-create a Stripe customer and pass its ID explicitly.

Do not attach both `customer_update` and `customer_creation`; Stripe will reject it.

## Webhook Handling

- `checkout.session.completed` activates add-ons matching the price lookup key and ties organizations to Stripe customers.
- Subscription lifecycle events (`customer.subscription.*`) keep billing status and `OrganizationAddon` rows in sync.
- Invoice events are stubbed today; extend `_handle_payment_succeeded`/`failed` when dunning is implemented.

## Common Failure Modes

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `Stripe lookup by lookup_key failed` | Tier stores a raw `price_*` ID or typo | Confirm the tier’s `stripe_lookup_key` matches a real lookup key or price ID |
| `customer_update can only be used with customer` | Payload requested `customer_update` without `customer` | Remove override or provide a concrete customer ID |
| HTTP 500 on signup redirect | Stripe API error creating session | Check Stripe dashboard logs; ensure environment variables (`STRIPE_SECRET_KEY`) are set |
| Add-on not activated after checkout | Price lookup key doesn’t match any `Addon` | Align lookup keys between Stripe and DB |

## Testing Checklist

1. Run `pytest tests/test_stripe_checkout_session.py` for price resolution and checkout payload guards.
2. Use `STRIPE_SECRET_KEY` + test keys to create a real Checkout Session locally (`flask shell` + invoke service) to verify environment configuration.
3. Hit `/billing/webhooks/stripe` with Stripe CLI replay if webhook handling changes.

## Touchpoints in Code

- `app/blueprints/auth/routes.py` – entry point creating checkout sessions.
- `app/services/billing_service.py` – Stripe API adapter, pricing cache, session creation, webhook handlers, and higher-level orchestration.
- `app/models/subscription_tier.py` – source of lookup keys and tier metadata.

Keep all future billing changes consistent with this flow to avoid the “circular fixes” we’ve seen in past incidents.
