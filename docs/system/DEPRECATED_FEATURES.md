# Deprecated Features Register

## Synopsis
This register tracks major removed/replaced feature surfaces so developers can avoid reintroducing retired paths or stale integration assumptions.

## Glossary
- **Deprecated**: Feature remains in code surface but is no longer preferred.
- **Removed**: Route/module was deleted and should not be referenced.
- **Replaced by**: Current authoritative system that supersedes the old behavior.

## Current Entries

### 1) Standalone density reference system
- **Status**: Replaced/removed as a standalone feature.
- **Legacy concept**: Dedicated density-reference route/data source.
- **Replaced by**:
  - Global library + ingredient-category density data.
  - API: `/api/ingredients/global-library/density-options`.
- **Current authority files**:
  - `app/blueprints/api/ingredient_routes.py`
  - `app/services/density_assignment_service.py`

### 2) Legacy batch plan template path
- **Status**: Replaced.
- **Legacy path reference**: `templates/components/batch/plan_batch.html`.
- **Current UI surface**:
  - `app/templates/pages/production_planning/plan_production.html`
  - `app/templates/partials/plan_production_stock_check.html`

### 3) Legacy density-route references in old UI snippets
- **Status**: Cleanup residue (not authoritative behavior).
- **Note**: Some template scripts still reference `/density-reference`; treat as legacy residue, not a source-of-truth route contract.

## How to Use This File
- Before adding new routes/services, check this file for retired names.
- Do not resurrect deprecated endpoints in new integrations.
- When deprecating a feature, add status + replacement path here in the same PR.

## Relevance Check (2026-02-17)
Validated against:
- `app/blueprints/api/ingredient_routes.py`
- `app/templates/pages/production_planning/plan_production.html`
- `app/templates/partials/plan_production_stock_check.html`
- `app/templates/inventory/components/edit_details_modal.html`
