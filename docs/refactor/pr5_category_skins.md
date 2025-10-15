# Category-driven Recipe Skins Refactor

## Summary
- Introduce a category skin layer on top of the canonical recipe form.
- Skins provide craft-specific UIs (baking, cosmetics) that translate into canonical ingredient lines and write structured metadata to recipe.category_data.
- Preserve a single backend model and one recipe form template.

## Goals
- Unify public tools and customer recipe experiences: same form, same behaviors.
- Eliminate duplicated calculators; centralize logic per category skin.
- Improve UX with domain-native inputs (percentages, base ingredients, batch size) while keeping outputs as explicit ingredient lines.
- Persist skin parameters in `recipe.category_data` for planning, labels, and exports.
- Allow users to toggle skins off (manual mode) any time.

## Architecture
- Canonical base: one `recipe_form.html`, one set of ingredient rows.
- Skins controller: `static/js/recipes/skins/category_skins.js` with `register(pattern, factory)`, `hasSkinFor`, `mount`, `unmount`.
- Skin host: `#categorySkinCard` and `#categoryInfoCard` injected in the form; skin mounts into host based on `Product Category`.
- Toggle: `Use category skin` switch; OFF reveals raw ingredient rows.
- Commit: skins compute and write ingredient rows (grams) and populate hidden inputs for `category_data[...]` keys.

## Data model (unchanged)
- `Recipe` + `RecipeIngredient` remain the only persisted entities for recipes.
- `Recipe.category_data` (JSON) stores structured skin metadata (see Key Map).

## Layout changes
- Portioning toggle moved inside Expected Yield card.
- Allowed Containers moved after Consumables; auto-hidden when portioned.
- Skin + Info cards appear when a skin exists for the selected category.

## Key map (category_data)
- Soaps (future in this refactor):
  - `superfat_pct`, `lye_concentration_pct`, `lye_type`
- Candles (future):
  - `fragrance_load_pct`
- Cosmetics/Lotions (this refactor):
  - `cosm_emulsifier_pct`, `cosm_preservative_pct`, `oil_phase_pct`, `water_phase_pct`, `cool_down_phase_pct`
- Baking (this refactor):
  - `base_ingredient_id` (FK), `moisture_loss_pct`, `derived_pre_dry_yield_g`, `derived_final_yield_g`
- Herbal (existing helper):
  - `herbal_ratio`

## Skin specs
### Baking skin
- Inputs: base ingredient (default Flour), base grams OR target final yield (g) + moisture loss %, percent or grams rows for other ingredients.
- Actions: Calculate → sets ingredient lines (grams) and fills Info card (moisture loss, pre-dry, final).
- Toggle: switch between % and grams input for non-base rows.
- Persist: bake-specific keys listed above.

### Cosmetics/Lotions skin
- Inputs: batch size (g), emulsifier %, preservative %, optional oil/water/cool-down % fields, optional percent rows per ingredient.
- Actions: Calculate → sets ingredient lines (grams), fills Info card with the defined cosmetics keys.
- Persist: cosmetics keys listed above.

## Implementation notes
- Units: commit as grams for determinism; user may change units on lines; Conversion Engine handles conversions with densities downstream.
- Manual mode: turning off the skin exposes canonical rows; re-enabling can recalc or mark out-of-sync.
- Public tools: may mount the same skins; tool drafts funnel into the same recipe form.

## Files
- `app/templates/pages/recipes/recipe_form.html` (layout changes and skin mount wiring)
- `app/static/js/recipes/skins/category_skins.js` (controller)
- `app/static/js/recipes/skins/baking_skin.js` (baking UI + logic)
- `app/static/js/recipes/skins/cosmetics_skin.js` (cosmetics UI + logic)
- `app/services/recipe_service/_core.py` (extended category_data allowlist)

## Rollout
1) Ship Baking + Cosmetics skins and layout changes.
2) Collect feedback, iterate on UX (percent/grams toggles, prepopulation from existing recipes).
3) Implement Soaps + Candles skins following this doc.
4) Remove legacy category aids once parity is reached.

## Test plan (high-level)
- Create baking recipe using skin: base flour + % rows; Calculate → rows/metadata correct; Save and re-edit.
- Toggle skin OFF → rows visible/editable; toggle ON → skin can re-derive.
- Create cosmetics recipe: batch size with %; Calculate → rows/metadata correct; Save and re-edit.
- Portioning ON hides containers; OFF shows containers; containers saved correctly.
- Ensure unit list is global-seeded; public tools mount consistent UI.
