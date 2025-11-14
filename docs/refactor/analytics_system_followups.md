## Analytics System Follow-Ups

### Current State
- `AnalyticsDataService` now exposes global inventory dashboards, organization dashboards, developer dashboards, waitlist analytics, dashboard alerts, fault logs, and system-wide counts with shared caching and refresh overrides.
- Developer inventory analytics, global item stats, organization dashboard, developer dashboard, waitlist stats, app dashboard alerts, and fault log views all read through the service, keeping results consistent and ready for future scaling.
- Caching uses short TTLs (30–300 s) with manual refresh hooks to support real-time feel without hammering the primary database.

### Next Steps (App Side)
- Expand the service to cover any remaining metrics that still query models directly (e.g. batch-level drill downs, customer support tooling, marketing analytics).
- Emit structured timestamps alongside payloads so templates can surface “Last updated” consistently.
- Add integration tests that hit the new endpoints and assert cache invalidation/refresh behaviour.
- Expose a developer-only endpoint or CLI hook that calls `AnalyticsDataService.invalidate_cache()` when large backfills run.

### Warehouse Readiness
- Outbox (`DomainEvent`) already captures key events; ensure ETL jobs publish them to the analytics warehouse once stood up.
- Mirror the `AnalyticsDataService` response shapes in warehouse models so the front-end can eventually switch to warehouse-backed APIs with minimal changes.
- Track cache misses/hits and DB timing so we know when to cut over to warehouse tables.

### Documentation & Ownership
- Keep `docs/system/TRACKING_PLAN.md` and `app/services/statistics/catalog.py` updated whenever new metrics are added to the service.
- Record future refactors or ownership changes in this document to maintain a single source of truth for analytics system plans.
