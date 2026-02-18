# 2026-02-18 — Recipe Group Insert Contention Hardening

## Summary
- Hardened recipe-group creation in recipe service core to reduce lock-driven p99 latency on concurrent recipe creation.
- Added retry-safe group insert handling with short lock-timeout, contention backoff, and race-safe reuse of already-created group rows.
- Added targeted tests to validate existing-group reuse and prefix collision fallback behavior.
- Fixed a lint-breaking undefined-name path in inventory adjustment core by restoring the missing tracking-policy import.

## Problems Solved
- A small set of recipe-creation calls showed high p99 tails where `recipe_group` inserts could block on contention.
- Group creation did not previously classify transient lock/deadlock/serialization failures as retryable in this flow.
- Documentation guard failures existed for missing functional-header blocks in new top-level helper units and stale APP_DICTIONARY route links.
- Lint (`ruff`) failed with `F821` in inventory adjustment core due a missing `org_allows_inventory_quantity_tracking` import.

## Key Changes
- `app/services/recipe_service/_core.py`
  - Added guarded helper units for group-name/prefix normalization, contention detection, and transaction-local lock-timeout management.
  - Updated `_ensure_recipe_group` to use nested insert attempts with retry/backoff and same-name reuse fallback.
  - Added required functional-unit header comments for new top-level helpers.
- `tests/test_recipe_group_creation.py`
  - Added regression tests for existing-name reuse and prefix collision regeneration during group creation.
- `docs/system/APP_DICTIONARY.md`
  - Updated stale route path references from legacy `app/routes/*` to active `app/blueprints/*` locations.
- `app/services/inventory_adjustment/_core.py`
  - Restored the missing `org_allows_inventory_quantity_tracking` import used by quantity-tracking gate checks.

## Files Modified
- `app/services/recipe_service/_core.py`
- `app/services/inventory_adjustment/_core.py`
- `tests/test_recipe_group_creation.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/2026-02-18-recipe-group-insert-contention-hardening.md` (this file)
- `docs/changelog/CHANGELOG_INDEX.md`
