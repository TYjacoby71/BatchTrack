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
- `app/templates/tools/soaps/index.html`
- `tests/test_soap_tool_compute_service.py` (new)
- `tests/test_soap_tool_lye_water.py` (new)
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`

## Impact
- Soap tool compute behavior now has a backend authority layer similar to service-oriented patterns used elsewhere.
- Front-end modules are more display-focused and easier to debug.
- Exported formula outputs now originate from the same canonical compute payload used for on-screen results.
