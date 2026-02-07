# 2026-02-06 — Recipe Lineage Notes, Prefix Auto-Generation, and Edit Overrides

## Summary
- Auto-generate recipe label prefixes from the recipe name and lock the field on new recipes.
- Lineage IDs now use organization-scoped group numbering with master/variation/test segments.
- Recipe view adds a notes panel plus a published-edit confirmation modal.
- New recipe groups can be named directly instead of auto-appending "New Group".

## Problems Solved
- New recipe groups were forced into "Old Name + New Group (N)".
- Label prefixes were entered manually, leading to collisions.
- Lineage IDs referenced global IDs instead of org-scoped group counts.
- Recipe notes were not visible or writable from the view screen.
- Published recipes could not be corrected without creating a new master.

## Key Changes
- `app/services/lineage_service.py`: added label prefix generator and org-scoped lineage IDs.
- `app/static/js/recipes/recipe_form.js`: auto-prefix logic for new recipes.
- `app/templates/pages/recipes/recipe_form.html`: locked prefix field with auto-generation.
- `app/templates/pages/recipes/view_recipe.html`: notes panel + edit confirmation modal.
- `app/services/recipe_service/_core.py`: edit override logging with timestamped notes.
- `app/blueprints/recipes/views/manage_routes.py`: new recipe note route and view wiring.
- `app/blueprints/recipes/views/create_routes.py`: forced edit path for published recipes.

## Impact
- Recipe lineage identifiers stay consistent within each organization.
- Teams can fix published typos with an explicit confirmation and audit trail.
- Notes are visible in the recipe view, improving traceability.
- New group naming is controlled by the user, not auto-suffixed.

## Files Modified
- `app/blueprints/api/routes.py`
- `app/blueprints/recipes/views/create_routes.py`
- `app/blueprints/recipes/views/manage_routes.py`
- `app/models/models.py`
- `app/services/lineage_service.py`
- `app/services/recipe_service/_core.py`
- `app/services/recipe_service/_helpers.py`
- `app/services/recipe_service/_versioning.py`
- `app/static/js/recipes/recipe_form.js`
- `app/templates/pages/recipes/recipe_form.html`
- `app/templates/pages/recipes/view_recipe.html`
- `app/utils/code_generator.py`
- `docs/system/API_REFERENCE.md`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-06-recipe-lineage-notes-and-prefixes.md` (this file)
