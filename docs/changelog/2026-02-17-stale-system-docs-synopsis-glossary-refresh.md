# 2026-02-17 — Stale System Docs Synopsis/Glossary Refresh

## Summary
- Refreshed the four stalest `docs/system/` guides (last touched 2025-10-29) to current documentation schema and implementation reality.
- Added required `## Synopsis` and `## Glossary` sections to each touched system document.
- Replaced stale path/command references and added explicit relevance checks tied to active code locations.

## Problems Solved
- Stale system docs lacked the current documentation guard schema expectations (`Synopsis`/`Glossary`) when touched.
- Legacy guidance drifted from current implementation details (notably container naming format and global item seeding commands).
- Several guides did not clearly show whether they were still mapped to active modules/routes.

## Key Changes
- `docs/system/CONTAINER_NAMING.md`
  - Added `Synopsis` and `Glossary`.
  - Updated canonical naming guidance to match `build_container_name` behavior.
  - Added relevance links to active creation/edit and display paths.
- `docs/system/DATABASE_MODELS.md`
  - Added `Synopsis` and `Glossary`.
  - Rebuilt model map around current `app/models/` modules and legacy compatibility notes.
  - Removed stale/ambiguous references and added active-source relevance check.
- `docs/system/GLOBAL_ITEM_JSON_STRUCTURE.md`
  - Added `Synopsis` and `Glossary`.
  - Updated seed file layout + schema notes to current `app/seeders/globallist/` usage.
  - Replaced outdated seeding command references with active CLI/script paths.
- `docs/system/GLOBAL_ITEM_LIBRARY.md`
  - Added `Synopsis` and `Glossary`.
  - Updated library/shelf architecture notes to current model/route/service locations.
  - Added current linkage, curation, and operations references.

## Files Modified
- `docs/system/CONTAINER_NAMING.md`
- `docs/system/DATABASE_MODELS.md`
- `docs/system/GLOBAL_ITEM_JSON_STRUCTURE.md`
- `docs/system/GLOBAL_ITEM_LIBRARY.md`
- `docs/changelog/2026-02-17-stale-system-docs-synopsis-glossary-refresh.md` (this file)
- `docs/changelog/CHANGELOG_INDEX.md`

