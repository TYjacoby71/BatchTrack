# 2026-02-09 — Lifetime Billing Alignment and Stripe Runbook

## Summary
- Aligned signup billing flow to the existing **single Stripe lookup key per tier** model.
- Removed the need for pricing-map environment configuration for yearly/lifetime key routing.
- Added a concrete Stripe production runbook to `docs/system/BILLING.md`.
- Removed the tier type selector from tier edit UI to reduce confusion in admin workflows.

## Problems Solved
- Confusion about whether yearly/lifetime lookup keys must be stored as additional tier fields.
- Drift toward config-heavy mappings that did not match current app architecture.
- Unclear operational guidance for safe Stripe price updates and lifetime counter continuity.

## Key Changes
- `app/services/lifetime_pricing_service.py`
  - Derives yearly/lifetime lookup keys from the tier's stored monthly key by naming convention.
  - Validates lifetime pricing against one-time Stripe billing cycle.
  - Keeps lifetime counter logic promo-code driven.
- `app/blueprints/auth/routes.py`
  - Uses derived lifetime keys for lifetime checkout override.
  - Fails safely when derived lifetime price is missing or not one-time.
- `app/templates/developer/edit_tier.html`
  - Removed tier type selector (`monthly/yearly/promotion`).
- `app/templates/developer/create_tier.html`
  - Clarified monthly-only key storage and derived yearly/lifetime behavior.
- `app/templates/developer/subscription_tiers.html`
  - Updated integration notes to Stripe product + three price-key pattern.
- `docs/system/BILLING.md`
  - Added step-by-step Stripe setup and operational instructions.

## Impact
- Tier admin remains simple: one Stripe lookup key per tier (`<slug>_monthly`).
- Signup can toggle monthly/yearly/lifetime without extra DB fields.
- Existing subscriptions remain unaffected by signup lookup-key changes.
- Documentation now reflects real production behavior and operator expectations.

## Files Modified
- `app/services/lifetime_pricing_service.py`
- `app/blueprints/auth/routes.py`
- `app/templates/developer/edit_tier.html`
- `app/templates/developer/create_tier.html`
- `app/templates/developer/subscription_tiers.html`
- `docs/system/BILLING.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-09-lifetime-billing-single-key-runbook.md` (this file)
