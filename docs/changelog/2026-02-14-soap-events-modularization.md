## Summary
- Refactored Soap Formulator frontend event wiring by splitting the monolithic events file into focused modules.
- Preserved runtime behavior while reducing coupling between row events, form bindings, export actions, mobile drawer logic, and startup initialization.
- Moved export rendering responsibility further toward backend/template ownership by removing large JS CSV/print fallback builders and introducing a server-rendered print-sheet template.
- Updated bundled soap assets and manifest mapping to ship the modularized structure.

## Problems Solved
- A single near-1k-line events file increased maintenance risk and made targeted edits harder to review.
- Mixed responsibilities in one module amplified merge conflict risk across parallel soap-tool changes.
- Startup and interaction wiring lacked clear boundaries for future feature additions.
- Export behavior duplicated domain logic in JavaScript instead of using service-owned payloads.
- Print sheet HTML layout lived in Python/JS string assembly instead of an HTML template.

## Key Changes
- Split soap event orchestration into dedicated modules:
  - `soap_tool_events_rows.js`
  - `soap_tool_events_forms.js`
  - `soap_tool_events_exports.js`
  - `soap_tool_events_mobile.js`
  - `soap_tool_events_init.js`
- Replaced the old large `soap_tool_events.js` body with a thin orchestrator that composes the new event modules.
- Simplified `soap_tool_events_exports.js` to consume service-provided `export.csv_text` and `export.sheet_html` only, including stale-calc detection before export actions.
- Refactored `app/services/tools/soap_tool/_sheet.py` to render print HTML through a dedicated template file.
- Added a new print export template at `app/templates/tools/soaps/exports/print_sheet.html`.
- Extracted stage row `<template>` markup into reusable template partial files for oils and fragrance rows.
- Updated `soap_tool_bundle_entry.js` imports to include the new module graph in deterministic order.
- Rebuilt hashed soap frontend assets and updated manifest mapping.

## Files Modified
- `app/static/js/tools/soaps/soap_tool_events.js`
- `app/static/js/tools/soaps/soap_tool_events_rows.js`
- `app/static/js/tools/soaps/soap_tool_events_forms.js`
- `app/static/js/tools/soaps/soap_tool_events_exports.js`
- `app/static/js/tools/soaps/soap_tool_events_mobile.js`
- `app/static/js/tools/soaps/soap_tool_events_init.js`
- `app/static/js/tools/soaps/soap_tool_bundle_entry.js`
- `app/services/tools/soap_tool/_sheet.py`
- `app/templates/tools/soaps/exports/print_sheet.html`
- `app/templates/tools/soaps/stages/partials/_oil_row_template.html`
- `app/templates/tools/soaps/stages/partials/_fragrance_row_template.html`
- `app/templates/tools/soaps/stages/_stage_2.html`
- `app/templates/tools/soaps/stages/_stage_5.html`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-FJ5WEHMO.js`
- `app/static/dist/manifest.json`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
