## Summary
- Refactored Soap Formulator frontend event wiring by splitting the monolithic events file into focused modules.
- Preserved runtime behavior while reducing coupling between row events, form bindings, export actions, mobile drawer logic, and startup initialization.
- Updated bundled soap assets and manifest mapping to ship the modularized structure.

## Problems Solved
- A single near-1k-line events file increased maintenance risk and made targeted edits harder to review.
- Mixed responsibilities in one module amplified merge conflict risk across parallel soap-tool changes.
- Startup and interaction wiring lacked clear boundaries for future feature additions.

## Key Changes
- Split soap event orchestration into dedicated modules:
  - `soap_tool_events_rows.js`
  - `soap_tool_events_forms.js`
  - `soap_tool_events_exports.js`
  - `soap_tool_events_mobile.js`
  - `soap_tool_events_init.js`
- Replaced the old large `soap_tool_events.js` body with a thin orchestrator that composes the new event modules.
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
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-QRFF44Q2.js`
- `app/static/dist/manifest.json`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
