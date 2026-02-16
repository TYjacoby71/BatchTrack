## Summary
- Fixed recipe test promotion naming so promoted versions no longer persist the `- Test N` suffix.
- Fixed recipe group list rendering so variation visibility is sourced from recipe-group lineage instead of a single master row relationship.
- Added regression coverage for both promotion-name reset and group-level variation display persistence.

## Problems Solved
- Promoting a master test to current could leave the persisted recipe name as `Group Name - Test N` instead of returning to the canonical master/group name.
- Recipe group cards/table rows could show zero variations after a master version migration because variation lookup depended on `parent_recipe_id` linkage to the previous master row.
- Recipe detail variation counts could drift from group lineage state after master promotions.

## Key Changes
- Updated `promote_test_to_current` to normalize promoted names:
  - Master test promotions now restore the recipe-group/master name.
  - Variation test promotions now restore the variation branch name.
  - Added test-suffix stripping fallback to prevent lingering test markers.
- Added group-scoped variation loading in recipe list management routes via `_group_variations_for_masters`.
- Updated recipe list template variation sections (card/table) to consume group-scoped variation payloads when present.
- Updated recipe detail variation counting to use current, non-test, non-archived group variations when recipe groups are enabled.
- Added targeted service and route-level regression tests for promotion naming and variation visibility after master test promotion.

## Files Modified
- `app/services/recipe_service/_versioning.py`
- `app/blueprints/recipes/views/manage_routes.py`
- `app/templates/pages/recipes/recipe_list.html`
- `tests/test_recipe_service_workflows.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
