## Summary
- Delivered recipe lineage UX updates for split New Test/New Variation actions, lineage tree placement, and streamlined lineage badges/history display.
- Enforced variation naming guardrails and promotion-name handling so group masters can retain canonical naming while variation branches stay unique.
- Aligned the PR with Documentation Guard requirements by adding missing functional header metadata and dictionary coverage entries.

## Problems Solved
- Recipe lineage actions mixed test and variation flows in one modal, which added friction and confusion for creators.
- Variation branch naming could drift into duplicate/case-fragmented branches within the same recipe group.
- Documentation Guard CI blocked merge because changed files lacked required Inputs/Outputs schema metadata and APP_DICTIONARY path coverage.

## Key Changes
- Updated recipe view and lineage templates to:
  - place lineage-tree navigation in the lineage selector area,
  - present dedicated New Test/New Variation actions with tooltips,
  - remove redundant lineage-origin/detail noise from the recipe detail surface, and
  - keep lineage tree badges focused on Master/Current markers.
- Updated lineage route/utilities to render variation-version stepping correctly and paginate lineage events.
- Updated recipe core/versioning logic to:
  - enforce case-insensitive variation branch checks,
  - preserve canonical naming during promotions, and
  - support duplicate-name override only for approved promotion paths.
- Added breadcrumb back-button fallback behavior in shared layout based on breadcrumb URL ancestry so detail pages can render consistent return affordances without route-by-route wiring.
- Added/updated APP_DICTIONARY entries for the touched lineage/core/alerts surfaces.

## Files Modified
- `app/blueprints/recipes/lineage_utils.py`
- `app/blueprints/recipes/views/lineage_routes.py`
- `app/services/recipe_service/_core.py`
- `app/services/recipe_service/_versioning.py`
- `app/templates/layout.html`
- `app/templates/pages/products/alerts.html`
- `app/templates/pages/recipes/recipe_lineage.html`
- `app/templates/pages/recipes/view_recipe.html`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
