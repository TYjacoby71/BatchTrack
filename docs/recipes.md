## Recipe Service Overview

The recipe domain is split between a thin blueprint (`app/blueprints/recipes/routes.py`) and the `app/services/recipe_service` package.  All external callers, including the blueprint, must import from `app.services.recipe_service` so that `_core`, `_validation`, `_scaling`, and `_batch_integration` remain internal implementation details.

- `_core.py` owns the public CRUD surface.  Helpers such as `_apply_marketplace_settings` and `_apply_portioning_settings` centralize behavior around sharing scope, marketplace metadata, and portion tracking so that both `create_recipe` and `update_recipe` stay DRY and only describe the high‑level flow.
- `_validation.py` is the single source of truth for payload validation.  It performs name, yield, ingredient, and portioning checks and returns a simple `{valid, error, missing_fields}` structure the routes can bubble back to the UI.
- `_scaling.py` and `_batch_integration.py` provide read-only utilities that operate on stored recipes.  They now rely on `Recipe.predicted_yield`/`predicted_yield_unit`, which keeps them aligned with the persisted schema used by batches and DTOs.

### Controller Responsibilities

`RecipeFormSubmission` (in `recipes/routes.py`) parses `request.form`/`request.files` into the exact kwargs expected by `create_recipe`/`update_recipe`.  It handles:

- Ingredient and consumable extraction via the existing helper functions.
- Portioning toggles, including on-the-fly creation of custom count units when a new portion label is entered.
- Marketplace/library controls through `RecipeMarketplaceService.extract_submission`, so every route—new recipe, variations, and edits—sends the same normalized metadata.

Because the parser always returns a complete payload, the route functions simply set route-specific context (e.g., `parent_recipe_id`, status mode, cloned source) and call the service.  This also fixed the regression where variations ignored public/private selections, since marketplace data is no longer optional per route.

### Lifecycle Notes

1. **Creation**
   - Blueprint parses the submission, passes it to `create_recipe`, and flashes any validation errors returned from `_validation`.
   - `_core` derives label prefixes, applies marketplace + portioning settings via helpers, persists row-level lineage metadata, and emits `recipe_created`.

2. **Updates**
   - Blueprint submits the same payload shape, adding the current recipe as the `existing` context so defaults are preserved when fields are omitted.
   - `_core.update_recipe` reuses the same helpers, guaranteeing that toggling marketplace scope or portioning always mutates both the JSON and discrete columns consistently.

3. **Utility Calls**
   - Scaling and batch preparation rely on the same predicted yield fields that feed batches/DTOs, preventing mismatches between “predicted” and “actual” yield semantics.

If additional routes or services need to mutate recipes, they should continue to go through the public functions exported from `app/services/recipe_service/__init__.py` so this contract remains enforced.  Any new form fields should be parsed in `RecipeFormSubmission` and normalized before hitting `_core`.
