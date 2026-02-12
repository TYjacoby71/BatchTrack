# Soap Tool Service Orchestration and JS Thinning

## Summary
Moved core soap-tool computation responsibilities into a dedicated backend service package and updated the front-end runner to consume structured service outputs instead of recomputing quality/additive/export logic in JavaScript.

## Problems Solved
- Soap tool calculations were fragmented across multiple JS files, making bug fixes hard to isolate and test.
- Export payload assembly (CSV/print sheet) was client-side and could drift from calculated values.
- The main runner remained oversized because orchestration and derived calculations were mixed with display updates.

## Key Changes
- Added a new service package: `app/services/tools/soap_tool/`
  - `_core.py`: canonical orchestration entrypoint (`SoapToolComputationService.calculate`)
  - `_lye_water.py`: canonical lye/water service authority
  - `_additives.py`: additive/fragrance normalization and output computation
  - `_fatty_acids.py`: iodine/fatty-acid/quality core math
  - `_quality_report.py`: warnings + visual guidance + quality bundle
  - `_sheet.py`: backend formula CSV rows/text + printable sheet HTML
  - `types.py`: normalized request contracts
- Updated `/tools/api/soap/calculate` to return the full orchestration bundle from `SoapToolComputationService`.
- Consolidated lye/water authority into `soap_tool/_lye_water.py` and removed the deprecated `soap_calculator` service package so there is one compute authority only.
- Updated soap runtime JS to consume backend-computed bundles:
  - runner now sends richer stage payloads (oils/fatty/fragrance/additives/meta)
  - result cards, quality data, and additive outputs now hydrate from service response
  - export actions prefer service-provided CSV and print-sheet outputs
- Split recipe payload assembly helpers out of `soap_tool_runner.js` into `soap_tool_recipe_payload.js` so runner orchestration is not coupled to draft/export DTO construction.
- Further thinned `soap_tool_runner.js` by extracting runner support concerns into dedicated modules:
  - `soap_tool_runner_inputs.js`: lye/water input sanitization, validation, and live preview helpers
  - `soap_tool_runner_quota.js`: calc quota/session tracking
  - `soap_tool_runner_service.js`: payload assembly + API transport
  - `soap_tool_runner_render.js`: service-result hydration into UI/state
  - `soap_tool_runner.js` now orchestrates those modules instead of carrying all concerns inline
- Added bulk-oils modal workflow for Stage 2:
  - new `/tools/api/soap/oils-catalog` endpoint returning basics/all oil catalogs with fatty-acid columns
  - searchable, sortable, lazy-rendered modal table with checkbox selection and optional `% total` / `weight` inputs
  - persisted bulk selection state in soap tool session storage until import
  - import action writes selected oils into Stage 2 rows without requiring weight/percent values
- Hardened bulk-oils catalog delivery and anti-scrape posture:
  - `/tools/api/soap/oils-catalog` now serves incremental server-side pages (`offset`/`limit`) capped at 25 rows per request
  - search (`q`) and sortable catalog fields (`sort_key`/`sort_dir`) are now server-side, so the browser only receives the current window
  - endpoint response no longer includes alias blobs, reducing unnecessary catalog surface in client payloads
  - tightened endpoint rate limit from blanket tool limits to a scroll-safe catalog-specific throttle (`1200/hour;120/minute`)
- Added hot-route caching and DB-index hardening for free-tool bulk-oils traffic:
  - oils-catalog now caches both merged source catalogs and paged responses using versioned global-library cache keys
  - cache invalidation is automatic when global items change because keys are namespaced through `global_library_cache_key(...)`
  - global catalog query switched to eager loading + `is_archived IS FALSE` filtering for index-friendly SQL
  - new migration `0024_global_item_soap_catalog_indexes` ensures composite and PostgreSQL partial indexes for active ingredient name scans
- Removed blocking/default-reset behavior from Stage 3 water-method inputs so typing is never overwritten mid-entry.
  - water % / concentration / ratio fields no longer force local preset values while typing
  - added per-method helper text showing normal ranges instead of preset enforcement
- Fixed `app/services/tools/soap_tool/_sheet.py` CSV escaping to avoid an f-string expression parsing edge in Python 3.11 CI validation.
- Added service-level tests for the new computation bundle and method-independent lye checks.

## Files Modified
- `app/routes/tools_routes.py`
- `app/services/tools/soap_tool/__init__.py` (new)
- `app/services/tools/soap_tool/_core.py` (new)
- `app/services/tools/soap_tool/_lye_water.py` (new)
- `app/services/tools/soap_tool/_additives.py` (new)
- `app/services/tools/soap_tool/_fatty_acids.py` (new)
- `app/services/tools/soap_tool/_quality_report.py` (new)
- `app/services/tools/soap_tool/_sheet.py` (new)
- `app/services/tools/soap_tool/types.py` (new)
- `app/services/tools/soap_calculator/__init__.py` (removed)
- `app/services/tools/soap_calculator/service.py` (removed)
- `app/services/tools/soap_calculator/types.py` (removed)
- `app/static/js/tools/soaps/soap_tool_runner.js`
- `app/static/js/tools/soaps/soap_tool_additives.js`
- `app/static/js/tools/soaps/soap_tool_quality.js`
- `app/static/js/tools/soaps/soap_tool_events.js`
- `app/static/js/tools/soaps/soap_tool_recipe_payload.js` (new)
- `app/static/js/tools/soaps/soap_tool_runner_inputs.js` (new)
- `app/static/js/tools/soaps/soap_tool_runner_quota.js` (new)
- `app/static/js/tools/soaps/soap_tool_runner_service.js` (new)
- `app/static/js/tools/soaps/soap_tool_runner_render.js` (new)
- `app/static/js/tools/soaps/soap_tool_bulk_oils_modal.js` (new)
- `app/static/js/tools/soaps/soap_tool_storage.js`
- `app/static/js/tools/soaps/soap_tool_units.js`
- `app/static/js/tools/soaps/soap_tool_runner_inputs.js`
- `app/static/css/tools/soaps.css`
- `app/templates/tools/soaps/index.html`
- `app/templates/tools/soaps/_modals.html`
- `app/templates/tools/soaps/stages/_stage_2.html`
- `app/templates/tools/soaps/stages/_stage_config.html`
- `tests/test_soap_tool_compute_service.py` (new)
- `tests/test_soap_tool_lye_water.py` (new)
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`

## Impact
- Soap tool compute behavior now has a backend authority layer similar to service-oriented patterns used elsewhere.
- Front-end modules are more display-focused and easier to debug.
- Exported formula outputs now originate from the same canonical compute payload used for on-screen results.
- Runner orchestration is now thinner and easier to reason about because transport/input/render/quota concerns are isolated in dedicated modules.
- Oil selection workflows now support high-volume catalog browsing and staged bulk import without forcing immediate weight/percent assignment.
- Water-method entry now behaves like free input during typing while still showing recommended ranges for safe formulation decisions.
