# 2026-02-17 — Stale System Docs Wave 2 Refresh (Next 10)

## Summary
- Refreshed the next 10 stalest `docs/system/*.md` files to current schema and current implementation behavior.
- Added required `## Synopsis` and `## Glossary` blocks to all touched docs.
- Replaced stale route/service/command references with active code paths and simplified outdated planning language into present-state guidance.

## Problems Solved
- Multiple older system docs contained stale assumptions (service names, route behavior, legacy planning text).
- Several docs lacked the current documentation schema expected by the documentation guard when touched.
- Operational docs drifted from active app behavior due to historical wording and deprecated references.

## Key Changes
- `docs/system/STORAGE_VS_DISPLAY.md`
  - Replaced stale helper references with active timezone utility/filter usage.
  - Consolidated guidance around current UTC-storage/user-display rule.
- `docs/system/TIMEZONE_SYSTEM.md`
  - Reframed as current architecture snapshot of timezone utilities, settings flows, and render boundaries.
- `docs/system/DEVELOPMENT_GUIDE.md`
  - Rebuilt around current engineering guardrails: service boundaries, scoping, permissions/billing policy, docs guard workflow.
- `docs/system/EXPORTS.md`
  - Updated route matrix and export behavior to match `exports_routes` + `ExportService`.
- `docs/system/FREE_TIER.md`
  - Updated to current `Free Tools` seeded tier semantics, permission-driven gating, billing policy, and public route boundaries.
- `docs/system/PLAN_SNAPSHOT.md`
  - Updated field/lifecycle mapping to active `PlanSnapshot` types and batch start orchestration.
- `docs/system/PUBLIC_TOOLS.md`
  - Updated public tool surfaces, soap APIs, draft handoff, quota note, and export linkage.
- `docs/system/TRACKING_PLAN.md`
  - Updated event transport/envelope model and currently emitted event families based on active emitters.
- `docs/system/DEPRECATED_FEATURES.md`
  - Replaced stale legacy file-path notes with current deprecation register and active replacements.
- `docs/system/SEO_ACCELERATION_PLAN.md`
  - Converted stale phased roadmap language into present-state SEO surface snapshot plus actionable backlog.

## Files Modified
- `docs/system/STORAGE_VS_DISPLAY.md`
- `docs/system/TIMEZONE_SYSTEM.md`
- `docs/system/DEVELOPMENT_GUIDE.md`
- `docs/system/EXPORTS.md`
- `docs/system/FREE_TIER.md`
- `docs/system/PLAN_SNAPSHOT.md`
- `docs/system/PUBLIC_TOOLS.md`
- `docs/system/TRACKING_PLAN.md`
- `docs/system/DEPRECATED_FEATURES.md`
- `docs/system/SEO_ACCELERATION_PLAN.md`
- `docs/changelog/2026-02-17-stale-system-docs-wave-2-refresh.md` (this file)
- `docs/changelog/CHANGELOG_INDEX.md`

