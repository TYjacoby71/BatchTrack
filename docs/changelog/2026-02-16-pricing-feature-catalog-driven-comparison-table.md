# 2026-02-16 — Pricing Feature Catalog-Driven Comparison Table

## Summary
- Refactored public pricing data assembly to use a curated customer-facing feature map rather than raw permission-name formatting.
- Added grouped comparison sections for capabilities and limits on `/pricing`.
- Added richer tier metadata to signup/pricing payloads (limits, add-ons, retention fields) to support structured feature rendering.

## Problems Solved
- Public pricing previously surfaced permission-derived labels that read as internal RBAC terms.
- Comparison rows lacked grouping and could not present numeric limits or retention policy as first-class pricing data.
- Tier highlights in pricing cards were not consistently aligned with customer-facing feature categories.

## Key Changes
- `app/services/signup_plan_catalog_service.py`
  - Added tier payload fields for:
    - limits (`max_recipes`, `max_batches`, `max_products`, `max_monthly_batches`, `max_batchbot_requests`, `user_limit`)
    - add-on keys/function keys/permission names (allowed + included + merged sets)
    - retention metadata (`retention_policy`, `retention_label`)
- `app/services/public_pricing_page_service.py`
  - Introduced grouped feature-section specs used to build comparison rows.
  - Added row evaluators for boolean capabilities and text-based limit/retention cells.
  - Added curated tier card highlights based on capabilities (inventory/FIFO, batches, products, marketplace, integrations, BatchBot, retention).
  - Updated tier resolution to prefer canonical tier-name mapping (`hobbyist` / `enthusiast` / `fanatic`) before lifetime-offer tier IDs so comparison section ordering stays consistent across all pricing sections.
- `app/templates/pages/public/pricing.html`
  - Updated comparison table to render grouped sections and mixed cell types (checkmarks + textual limits/policies).
  - Updated copy from generic feature checklist language to customer-facing “features and limits” language.

## Impact
- `/pricing` now communicates plan differentiation in product-language terms.
- Limits and retention policy are visible directly in the comparison table.
- Tier cards and comparison content are better aligned with subscription packaging strategy.

## Files Modified
- `app/services/signup_plan_catalog_service.py`
- `app/services/public_pricing_page_service.py`
- `app/templates/pages/public/pricing.html`
- `docs/changelog/2026-02-16-pricing-feature-catalog-driven-comparison-table.md` (this file)

