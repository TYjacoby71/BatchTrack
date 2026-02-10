# 2026-02-10 — Landing Page A/B Variants + Metadata/Dictionary Alignment

## Summary
- Added two public landing-page variants for A/B testing:
  - `/lp/hormozi` (results-first offer framing)
  - `/lp/robbins` (transformation-first calm workflow framing)
- Wired both routes into the public route registry and access middleware allow-list.
- Added maker-first metadata context for both routes (`page_title`, `page_description`, `canonical_url`, and `page_og_image`).
- Updated app dictionary entries for the new routes and UI surfaces.
- Updated SEO guide examples with metadata references for both new landing variants.

## Problems Solved
- No dedicated split-test landing destinations existed for distinct messaging styles.
- Public-access guardrails did not explicitly include the new `/lp/*` endpoints.
- Documentation/checklist requirements for dictionary and metadata references were incomplete for the new surfaces.

## Key Changes
- `app/routes/landing_routes.py`
  - Added `/lp/hormozi` and `/lp/robbins` route handlers.
  - Added maker-first metadata context and OG image assignment per route.
  - Added file synopsis/glossary and top-level purpose headers.
- `app/templates/pages/public/landing_hormozi.html`
  - Added a public results-first landing variant for small-batch makers.
  - Added file synopsis/glossary block.
- `app/templates/pages/public/landing_robbins.html`
  - Added a public transformation-first landing variant for small-batch makers.
  - Added file synopsis/glossary block.
- `app/blueprints_registry.py`
  - Registered `landing_pages_bp` blueprint.
- `app/route_access.py`
  - Added `landing_pages.lp_hormozi` and `landing_pages.lp_robbins` to `PUBLIC_ENDPOINTS`.
  - Added `/lp/` prefix to `PUBLIC_PATH_PREFIXES`.
- `tests/test_public_tools_access.py`
  - Added anonymous access assertions for `/lp/hormozi` and `/lp/robbins`.
- `docs/system/APP_DICTIONARY.md`
  - Added dictionary entries for the new landing routes and landing UI variants.
  - Added operations entry for landing route metadata context.
- `docs/system/SEO_GUIDE.md`
  - Added page metadata examples for both new landing variants.

## Impact
- Marketing now has two dedicated public variants to run clean A/B campaigns against the same signup flow.
- Route access policy remains explicit and deterministic for unauthenticated traffic.
- Metadata and dictionary standards are aligned with project documentation and PR checklist expectations.

## Files Modified
- `app/routes/landing_routes.py`
- `app/templates/pages/public/landing_hormozi.html`
- `app/templates/pages/public/landing_robbins.html`
- `app/blueprints_registry.py`
- `app/route_access.py`
- `tests/test_public_tools_access.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/system/SEO_GUIDE.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-10-landing-page-ab-variants-and-metadata-dictionary-alignment.md` (this file)
