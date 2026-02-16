# 2026-02-14: Soap Backend Policy Injection + Recipe Payload API

## Summary
- Moved remaining soap-tool policy/constants ownership to backend-injected config consumed by the frontend.
- Added a dedicated backend endpoint that assembles soap recipe payloads from calculation snapshots and draft-line context.
- Kept the soap UI display unchanged while reducing browser-side domain assembly logic.

## Problems Solved
- Removed hardcoded policy/config drift risk in `soap_tool_constants.js` by injecting backend-owned policy JSON in `tools/soaps/index.html`.
- Eliminated browser-side recipe payload assembly duplication by moving canonical payload composition to Python service code.
- Added a public tool API for recipe payload generation to keep save/export workflows aligned with service-layer rules.

## Key Changes
- Added `app/services/tools/soap_tool/_policy.py` as the canonical soap policy source for ranges, hints, presets, category filters, and stage config.
- Added `app/services/tools/soap_tool/_recipe_payload.py` to build normalized soap draft payloads (ingredients/consumables/containers/category data/notes blob).
- Exposed policy and payload builders via `app/services/tools/soap_tool/__init__.py`.
- Updated `app/routes/tools_routes.py`:
  - `/tools/soap` now injects `soap_policy`.
  - Added `POST /tools/api/soap/recipe-payload`.
- Updated frontend soap modules:
  - `soap_tool_constants.js` now consumes `window.soapToolPolicy` with safe fallbacks.
  - `soap_tool_runner_service.js` now posts to `/tools/api/soap/recipe-payload`.
  - `soap_tool_recipe_payload.js` now builds request context only (no recipe payload assembly).
  - `soap_tool_runner.js` now calls service-backed payload assembly.
  - `soap_tool_events_exports.js` save action now awaits service-built payloads.
  - `soap_tool_additives.js` now returns fragrance/additive metadata needed by backend payload assembly.
- Added public access coverage tests for policy injection and recipe payload API.

## Files Modified
- `app/routes/tools_routes.py`
- `app/services/tools/soap_tool/__init__.py`
- `app/services/tools/soap_tool/_additives.py`
- `app/services/tools/soap_tool/_policy.py`
- `app/services/tools/soap_tool/_quality_report.py`
- `app/services/tools/soap_tool/_recipe_payload.py`
- `app/services/tools/soap_tool/types.py`
- `app/static/js/tools/soaps/soap_tool_additives.js`
- `app/static/js/tools/soaps/soap_tool_constants.js`
- `app/static/js/tools/soaps/soap_tool_events_exports.js`
- `app/static/js/tools/soaps/soap_tool_recipe_payload.js`
- `app/static/js/tools/soaps/soap_tool_runner.js`
- `app/static/js/tools/soaps/soap_tool_runner_service.js`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-4ZLLWQHL.js`
- `app/static/dist/manifest.json`
- `app/templates/tools/soaps/index.html`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/system/APP_DICTIONARY.md`
- `tests/test_public_tools_access.py`
