## Summary
- Added a print-time mold-fill confirmation modal to the Soap Formulator finalize flow.
- Kept live stage editing fully reactive while moving normalization decisions to print finalization.
- Added optional print-time normalization to scale batch ingredients to a chosen mold-fill target.

## Problems Solved
- Users could reach print with formulas that underfilled or overflowed mold capacity without a final confirmation gate.
- Existing reactive stage flow had no low-friction finalization checkpoint for mold-fit decisions.
- Print output lacked a controlled option to proportionally normalize formula quantities at finalization time.

## Key Changes
- Added `#soapPrintConfirmModal` to show batch yield, mold capacity, fill percentage, and over/under difference when printing.
- Added print-time threshold logic in the soap tool events module so the modal only appears outside the configured range (`<90%` or `>120%`).
- Added normalization support from the modal to scale oils, lye, water, fragrance, and additives to a user-entered mold-fill percent before generating the print sheet.
- Added normalization context text into the printed sheet when scaled output is selected.
- Rebuilt hashed frontend assets so the runtime and manifest map to the new soap-tool behavior.

## Files Modified
- `app/templates/tools/soaps/_modals.html`
- `app/static/js/tools/soaps/soap_tool_events.js`
- `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-3ZBTVXIO.js`
- `app/static/dist/manifest.json`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
