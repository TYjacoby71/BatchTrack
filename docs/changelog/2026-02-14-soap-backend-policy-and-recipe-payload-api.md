# 2026-02-14: Soap Backend Policy Injection + Recipe Payload/API Authority

## Summary
- Moved soap policy/default ownership to backend-injected config consumed by frontend modules.
- Added backend recipe-payload and quality-nudge APIs so browser code no longer owns those domain assemblies.
- Shifted blend-tip and quality-nudge advisory logic out of JS and into backend service authority while preserving the same UI display.

## Problems Solved
- Removed policy drift risk by centralizing defaults/ranges/factors in `app/services/tools/soap_tool/_policy.py`.
- Eliminated browser-side recipe payload composition duplication by moving canonical payload assembly to Python.
- Fixed citric-acid KOH multiplier mismatch by using one backend-owned factor map (`NaOH=0.624`, `KOH=0.71`) across service and JS preview wiring.
- Removed string-built shell markup for soap alert/list surfaces by introducing hidden client template partials.
- Moved quality-target nudge and oil blend-tip heuristics out of frontend domain logic into backend service functions/endpoints.

## Key Changes
- Added policy/config authority:
  - `app/services/tools/soap_tool/_policy.py` now includes quality policy, category filters, citric factors, and default input values.
  - `tools/soap` route injects the policy JSON to `window.soapToolPolicy`.
- Added backend advisory authority:
  - New `app/services/tools/soap_tool/_advisory.py` with blend-tip and quality-nudge computation.
  - New `POST /tools/api/soap/quality-nudge` endpoint.
  - Quality report now includes backend-generated `blend_tips`.
- Continued payload migration:
  - `POST /tools/api/soap/recipe-payload` remains the canonical payload builder path.
  - Frontend save/export path now sends context and receives backend-built payloads.
- Reduced frontend domain duplication:
  - `soap_tool_quality.js` now requests backend nudge results instead of computing nudge math in-browser.
  - `soap_tool_oils.js` now renders backend-provided blend tips.
  - `soap_tool_additives.js` now uses policy-injected citric factors.
  - Stage reset/storage fallbacks now read policy-injected defaults instead of hardcoded literals.
- Templateized JS-rendered shell markup:
  - Added `app/templates/tools/soaps/_client_templates.html`.
  - `soap_tool_ui.js`, `soap_tool_quality.js`, and `soap_tool_oils.js` now render from template/DOM nodes instead of shell `innerHTML` strings.
- Added/updated coverage:
  - Public tests for policy injection, recipe payload API, and quality-nudge API.
  - Advisory unit coverage for quality nudge output contract.

## Files Modified
- `app/routes/tools_routes.py`
- `app/services/tools/soap_tool/__init__.py`
- `app/services/tools/soap_tool/_additives.py`
- `app/services/tools/soap_tool/_advisory.py`
- `app/services/tools/soap_tool/_policy.py`
- `app/services/tools/soap_tool/_quality_report.py`
- `app/services/tools/soap_tool/_recipe_payload.py`
- `app/services/tools/soap_tool/types.py`
- `app/static/js/tools/soaps/soap_tool_additives.js`
- `app/static/js/tools/soaps/soap_tool_constants.js`
- `app/static/js/tools/soaps/soap_tool_events_exports.js`
- `app/static/js/tools/soaps/soap_tool_oils.js`
- `app/static/js/tools/soaps/soap_tool_quality.js`
- `app/static/js/tools/soaps/soap_tool_recipe_payload.js`
- `app/static/js/tools/soaps/soap_tool_runner.js`
- `app/static/js/tools/soaps/soap_tool_runner_inputs.js`
- `app/static/js/tools/soaps/soap_tool_runner_render.js`
- `app/static/js/tools/soaps/soap_tool_runner_service.js`
- `app/static/js/tools/soaps/soap_tool_stages.js`
- `app/static/js/tools/soaps/soap_tool_storage.js`
- `app/static/js/tools/soaps/soap_tool_ui.js`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-4ZLLWQHL.js`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-YBBGVXEH.js`
- `app/static/dist/manifest.json`
- `app/templates/tools/soaps/_client_templates.html`
- `app/templates/tools/soaps/index.html`
- `app/templates/tools/soaps/stages/_stage_1.html`
- `app/templates/tools/soaps/stages/_stage_4.html`
- `app/templates/tools/soaps/stages/_stage_config.html`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/system/APP_DICTIONARY.md`
- `tests/test_public_tools_access.py`
- `tests/test_soap_tool_compute_service.py`
