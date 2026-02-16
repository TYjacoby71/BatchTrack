# Soap Guidance Dock Consolidation (Stage + Quality Hint Unification)

## Summary
Consolidated soap formulator hints/guidance into one bottom, full-width guidance dock that expands upward over the stage/quality region and collapses back to a single-line bar. This removes scattered hint surfaces from stage cards and quality rows while preserving trigger logic from the active formula configuration.

## Problems Solved
- Guidance was fragmented across stage cards, quality rows, and multiple lower-page blocks, making it hard to scan.
- Users had to hunt for context-sensitive hints in several places after each input change.
- Bottom guidance sections and in-card hints could duplicate intent while increasing visual noise.

## Key Changes
- Added a dedicated guidance module: `app/static/js/tools/soaps/soap_tool_guidance.js`.
  - Central section registry for active hints/warnings/tips.
  - Single-line summary state with active hint counts.
  - Expand/collapse controller with caret toggle and accessibility attributes.
- Replaced the former “Guidance & Actions” card with a docked/overlay panel in `app/templates/tools/soaps/_results_actions_card.html`.
  - Dock remains visible as one row in collapsed state.
  - Expanded state opens upward and overlays the stage/quality working area.
  - Existing action buttons remain in the expanded panel.
- Rerouted scattered hint writers into centralized guidance sections:
  - Stage 2 oil entry limits/warnings/tips (`soap_tool_oils.js`).
  - Stage 3 lye-purity and water-method hints (`soap_tool_runner_inputs.js`).
  - Quality feel hints and service warning flags (`soap_tool_quality.js`).
  - Visual guidance payload rendering (`soap_tool_additives.js`).
  - Water concentration/ratio warning copy (`soap_tool_ui.js`).
- Removed inline quality hint rows and stage-card hint placeholders from templates.
- Added guidance overlay height sync in `soap_tool_layout.js` to match stage/quality row height.
- Rebuilt soap static assets and manifest for hashed delivery.

## Files Modified
- `app/static/js/tools/soaps/soap_tool_guidance.js` (new)
- `app/static/js/tools/soaps/soap_tool_bundle_entry.js`
- `app/static/js/tools/soaps/soap_tool_runner_inputs.js`
- `app/static/js/tools/soaps/soap_tool_oils.js`
- `app/static/js/tools/soaps/soap_tool_additives.js`
- `app/static/js/tools/soaps/soap_tool_quality.js`
- `app/static/js/tools/soaps/soap_tool_ui.js`
- `app/static/js/tools/soaps/soap_tool_layout.js`
- `app/templates/tools/soaps/_results_actions_card.html`
- `app/templates/tools/soaps/_quality_card.html`
- `app/templates/tools/soaps/stages/_stage_2.html`
- `app/templates/tools/soaps/stages/_stage_config.html`
- `app/static/css/tools/soaps.css`
- `app/static/css/tools/soaps.min.css`
- `app/static/dist/manifest.json`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-FCLB3YPR.js`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`

## Impact
- Soap-tool guidance is now centralized and easier to consume during iterative formulation.
- Active hints remain configuration-driven but no longer compete with in-card layout density.
- The stage/quality work area stays cleaner, with guidance intentionally grouped in one controlled panel.
