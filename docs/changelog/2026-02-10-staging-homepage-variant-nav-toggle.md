# 2026-02-10 — Staging Homepage Variant Toggle in Public Nav

## Summary
- Added a staging-only "Home Variants" dropdown to the public marketing header.
- The dropdown links to:
  - classic homepage (`/`)
  - results-first landing variant (`/lp/hormozi`)
  - transformation-first landing variant (`/lp/robbins`)
- Added test coverage to verify the switcher is hidden outside staging and visible in staging.

## Problems Solved
- Staging reviewers could not quickly switch between homepage variants from the nav.
- Manual URL edits were required to move between classic and A/B landing versions.

## Key Changes
- `app/templates/components/shared/public_marketing_header.html`
  - Added staging environment detection via template config context.
  - Added "Home Variants" dropdown shown only when `ENV/FLASK_ENV == staging`.
- `tests/test_public_tools_access.py`
  - Added `test_staging_homepage_variant_switcher_visibility`.
  - Validates non-staging hides the switcher and staging shows links to `/lp/hormozi` and `/lp/robbins`.
- `docs/system/APP_DICTIONARY.md`
  - Added a UI glossary entry for the staging homepage variant switcher.

## Impact
- Staging QA and stakeholders can toggle homepage variants without leaving the nav flow.
- Production users do not see experiment navigation.

## Files Modified
- `app/templates/components/shared/public_marketing_header.html`
- `tests/test_public_tools_access.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-10-staging-homepage-variant-nav-toggle.md` (this file)
