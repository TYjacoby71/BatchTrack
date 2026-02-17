# 2026-02-16 — Tier Feature Catalog and Entitlement Mapping Rules

## Summary
- Added a new system document that defines a customer-facing feature catalog for pricing and tier design.
- Mapped feature labels to underlying permissions, add-ons, feature flags, and numeric limits.
- Documented which limits are hard-enforced today versus currently metadata-only.
- Added recommended tier-construction dependency rules (multi-user, BatchBot, marketplace, retention, and bulk operations).

## Problems Solved
- Subscription tier planning lacked one canonical place that translates internal permission keys into customer-readable features.
- Pricing content risked drifting between "raw permissions" and "feature outcomes."
- Limit semantics (enforced vs non-enforced) were not clearly documented for commercial packaging decisions.

## Key Changes
- `docs/system/TIER_FEATURE_CATALOG.md`
  - Added full feature taxonomy across inventory, recipes, batches, products, organization, marketplace, public tools, AI, reporting, and retention.
  - Added entitlement layer model (permissions, add-ons, flags, limits).
  - Added enforcement matrix for tier limit fields.
  - Added tier dependency rule recommendations and pricing presentation guidance.
- `docs/system/SYSTEM_INDEX.md`
  - Added the new feature catalog document to the Product Programs & Feature Toggles section.

## Impact
- Product, growth, and engineering now share a single reference for building consistent pricing tables and subscription packaging.
- Reduces ambiguity around what to market as a feature versus what to keep internal as a permission key.
- Provides a concrete baseline for future implementation work (for example, enforcing currently metadata-only limits).

## Files Modified
- `docs/system/TIER_FEATURE_CATALOG.md`
- `docs/system/SYSTEM_INDEX.md`
- `docs/changelog/2026-02-16-tier-feature-catalog-and-mapping-rules.md` (this file)

