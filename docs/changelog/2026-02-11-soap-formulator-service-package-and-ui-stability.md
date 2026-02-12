## Summary
This change set stabilizes and structures the public soap formulator by extracting lye/water math into a tool-scoped service package, adding a public calculation API, and resolving multiple UI/UX issues in stage navigation and quality presentation.

## Problems Solved
- Eliminated duplicated lye/water calculation paths in the browser that could drift from intended behavior.
- Added a canonical soap calculation service boundary for a clearer architecture and easier testing.
- Fixed stage-card usability and visual clarity issues (internal scroll, preset marker contrast, validation icon overlap).
- Improved lye/water stage visibility by showing calculated water directly in the stage where users choose water method.

## Key Changes
- Introduced `app/services/tools/soap_calculator/` package with typed request/result contracts and deterministic `SoapToolCalculatorService`.
- Added `POST /tools/api/soap/calculate` route in `app/routes/tools_routes.py` and allowed public access via `app/route_access.py`.
- Updated `soap_tool_runner.js` to call the service API as the source of truth and removed duplicated frontend lye/water formula functions from `soap_tool_calc.js`.
- Added/updated tests for the new service and public tool API.
- Completed soap UI improvements in stage synchronization, stage-card scroll behavior, quality marker visibility, and suffix/icon spacing.

## Files Modified
- `app/routes/tools_routes.py`
- `app/route_access.py`
- `app/services/tools/__init__.py`
- `app/services/tools/soap_calculator/__init__.py`
- `app/services/tools/soap_calculator/service.py`
- `app/services/tools/soap_calculator/types.py`
- `app/static/js/tools/soaps/soap_tool_calc.js`
- `app/static/js/tools/soaps/soap_tool_core.js`
- `app/static/js/tools/soaps/soap_tool_events.js`
- `app/static/js/tools/soaps/soap_tool_mold.js`
- `app/static/js/tools/soaps/soap_tool_oils.js`
- `app/static/js/tools/soaps/soap_tool_runner.js`
- `app/static/js/tools/soaps/soap_tool_storage.js`
- `app/static/css/tools/soaps.css`
- `app/templates/tools/soaps/stages/_stage_config.html`
- `app/templates/layout.html`
- `tests/test_public_tools_access.py`
- `tests/test_soap_tool_calculator_service.py`
