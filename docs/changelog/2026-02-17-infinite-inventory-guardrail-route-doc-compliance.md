## Summary
- Aligned recently touched batch and production-planning route modules with Documentation Guard functional-unit schema requirements.
- Added missing APP_DICTIONARY route coverage entries for the batch start/finish and production-planning route files touched by the infinite-inventory follow-up changes.
- Added this dated changelog entry so app-code changes remain traceable and guard-compliant.

## Problems Solved
- Documentation Guard was failing for the latest commit scope because top-level route/helper units in touched files were missing required header metadata (`Purpose`, `Inputs`, `Outputs`).
- APP_DICTIONARY coverage checks failed because touched route modules were not referenced in dictionary entries.
- PR-level changelog requirement was unmet for app-code updates in the latest commit scope.

## Key Changes
- Added required functional-unit header blocks to:
  - `app/blueprints/batches/finish_batch.py`
  - `app/blueprints/batches/routes.py`
  - `app/blueprints/batches/start_batch.py`
  - `app/blueprints/production_planning/routes.py`
- Added new route-layer dictionary entries in `docs/system/APP_DICTIONARY.md` that explicitly reference:
  - `app/blueprints/batches/routes.py`
  - `app/blueprints/batches/start_batch.py`
  - `app/blueprints/batches/finish_batch.py`
  - `app/blueprints/production_planning/routes.py`
- Recorded the guard-alignment work in this changelog artifact.

## Files Modified
- `app/blueprints/batches/finish_batch.py`
- `app/blueprints/batches/routes.py`
- `app/blueprints/batches/start_batch.py`
- `app/blueprints/production_planning/routes.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/2026-02-17-infinite-inventory-guardrail-route-doc-compliance.md`
