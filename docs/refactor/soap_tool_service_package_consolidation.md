# Soap Tool Service Package Consolidation

## Synopsis
This document defines the soap-tool consolidation pattern that moves domain calculations out of UI JavaScript and into a backend service package, while keeping the front end focused on interaction and rendering.

## Glossary
- **Canonical compute bundle**: Single backend response containing all derived soap outputs (lye/water, additives, quality, exports).
- **Stage payload**: Aggregated inputs collected from soap tool stages before computation.
- **Render-only UI**: Front-end modules that display service results without re-implementing core math.

## Current-State Diagnosis
- Soap calculations were split between:
  - backend lye/water service,
  - frontend quality/additive math,
  - frontend export-sheet assembly.
- This caused high coupling and slow troubleshooting because one formula bug could involve multiple JS modules.

## Target Architecture
Use a dedicated backend package:

`app/services/tools/soap_tool/`

- `types.py` → normalized request contracts
- `_lye_water.py` → canonical lye/water bridge
- `_additives.py` → additive/fragrance totals and adjustments
- `_fatty_acids.py` → fatty acid and quality primitives
- `_quality_report.py` → warnings, guidance, and quality payload
- `_sheet.py` → export CSV rows/text and printable sheet HTML
- `_core.py` → orchestration entrypoint

Entrypoint:
- `SoapToolComputationService.calculate(payload) -> dict`

## Frontend Responsibility Split
- JS should own:
  - stage events and interaction timing,
  - input mirroring and UX validation,
  - rendering cards/charts/alerts from service payloads.
- JS should not own:
  - canonical formula math,
  - quality warning rule engines,
  - export payload assembly logic.

## API Contract Direction
- `/tools/api/soap/calculate` should return a full compute bundle:
  - existing lye/water fields (compatibility),
  - `additives`,
  - `quality_report`,
  - `results_card`,
  - `export` (CSV + sheet HTML).

## Why This Pattern
- Centralized calculations improve testability and reduce drift.
- UI becomes easier to maintain because display logic can be patched without touching formula authority.
- Export output consistency improves because on-screen values and exported values share one backend source.

