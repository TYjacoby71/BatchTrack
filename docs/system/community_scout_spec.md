## Community Scout Specification

### Objectives
- Surface organization-level inventory items that are not yet represented in the Global Inventory Library (GIL).
- Highlight two buckets: `Truly Unique` (no meaningful match) and `Needs Review` (matching confidence above threshold) to help dev reviewers either promote or link items.
- Minimize impact on primary database by running heavy discovery in off-hours using read replicas and batching.
- Feed accepted matches back into the existing Global Link workflow so affected organizations immediately see the drawer prompt.

### High-Level Architecture
1. **Background discovery job (Celery scheduled)**
   - Runs nightly (configurable cadence) during a low-usage window.
   - Reads from a replica database connection to avoid stressing the primary writer node.
   - Iterates over org inventories in pages, builds normalized tokens, evaluates similarity against GIL entries, and emits scored candidates into a persistent queue.
2. **Community Scout API (dev-only)**
   - Serves precomputed batches (default batch size 100) from the queue.
   - Accepts reviewer actions (`promote_to_global`, `link_existing`, `reject`, `flag_alias`) and forwards them to existing services (GlobalItemService, GlobalLinkSuggestionService) so workflows stay centralized.
3. **Dev navigation UI**
   - New `Community Scout` link placed under the Global Inventory Library section.
   - Page loads the next available batch, shows `Unique` vs `Needs Review`, and exposes action buttons.
   - Provides alias-moderation controls when offensive or sensitive aka matches are present.

### Data Model Additions
| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `community_scout_batches` | Stores batch metadata and progress | `id`, `status` (`pending`, `in_review`, `completed`), `generated_at`, `processed_at`, `generated_by_job_id`, `notes` |
| `community_scout_candidates` | Individual org inventory candidates tied to a batch | `id`, `batch_id`, `organization_id`, `inventory_item_id`, `item_snapshot_json`, `classification` (`unique`, `needs_review`), `match_scores` JSON (name, aka, inci, phonetic, category, unit), `sensitivity_flags`, `state` (`open`, `resolved`, `skipped`), `resolved_by`, `resolved_at`, `resolution_payload` |
| `community_scout_job_state` | Tracks pagination checkpoints per run | `job_name`, `last_inventory_id_processed`, `last_run_at`, `lock_expires_at` |

- `item_snapshot_json` stores denormalized fields (original name, normalized tokens, units, INCI, type) so the UI does not need live joins.
- `match_scores` includes the top-N global item ids with weighted scores to display to reviewers.
- `sensitivity_flags` notes hits on banned/offensive AKA strings.

### Matching Pipeline
1. **Extraction**
   - Fetch unlinked inventory items (`global_item_id IS NULL`, `is_archived = false`) per organization in pages of 500 to keep memory bounded.
2. **Normalization**
   - Lowercase, trim, remove diacritics, handle plural stripping.
   - Detect language (fastText-lite or existing language util) and translate common terms to English tokens using a lightweight dictionary so words like “leche” map to “milk”.
   - Expand synonyms using the existing aka list plus configurable dictionaries (e.g., INCI <-> common name).
3. **Signal scoring**
   - `exact_match` (1.0) if normalized equals GIL name.
   - `aka_match` (0.95) if any alias equals the name.
   - `inci_match` (0.9) if INCI names match.
   - `phonetic/Levenshtein` score (0-0.85) using existing density similarity helper.
   - `category/unit compatibility` bonus when types/units align.
   - Weighted sum yields final confidence (0-1). Threshold defaults: `>=0.65` → `needs_review`, `<0.65` → `unique`.
4. **Sensitivity check**
   - If a name matches an AKA flagged as offensive/legacy, set `sensitivity_flags` so the UI forces moderation before promotion.
5. **Batch assembly**
   - Collect candidates until 100 entries per batch, store to `community_scout_batches` & `community_scout_candidates`.

### Background Job Flow
1. Celery beat schedules `community_scout_generate_batches` nightly (configurable).
2. Worker acquires a row-level lock in `community_scout_job_state` to prevent concurrent runs.
3. Uses replica DB URL (configuration key `COMMUNITY_SCOUT_READ_DSN`). If unavailable, job aborts early with warning to avoid stressing primary.
4. Pages through inventory data ordered by `id`, resuming from `last_inventory_id_processed`.
5. After each batch insert, commit and emit metrics (`batch_count`, `candidate_count`, `duration_ms`).
6. At completion (or when time window expires), update checkpoint and release lock.
7. Job never mutates inventory/global tables—only writes to its own tables.

### API Contracts (dev-authenticated only)
- `GET /api/dev/community-scout/batches/next`
  - Returns next batch metadata + candidates grouped by `classification`.
  - Supports `?status=pending|in_review` (default pending). Automatically marks batch as `in_review` once served.
- `POST /api/dev/community-scout/candidates/<id>/promote`
  - Payload: `{ "global_item_payload": {...}, "moderated_aliases": [...], "notes": "" }`
  - Creates new GlobalItem via existing service, logs resolution, triggers Global Link drawer for orgs with same normalized name.
- `POST /api/dev/community-scout/candidates/<id>/link`
  - Payload: `{ "global_item_id": 123, "notes": "" }`
  - Calls GlobalLinkSuggestionService to update the org inventory item and queue drawer notifications.
- `POST /api/dev/community-scout/candidates/<id>/reject`
  - Marks state as `resolved` with reason (e.g., “junk”, “needs more data”).
- `POST /api/dev/community-scout/candidates/<id>/flag`
  - Allows devs to flag offensive aliases for moderation without immediate promotion.
- All endpoints require dev/admin permission (e.g., `global_inventory.manage`).

### UI Integration
- Add a Dev-only nav link: `Global Inventory Library > Community Scout`.
- Page layout:
  1. Batch header (timestamp, item counts, navigation between batches).
  2. Tabs or accordion for `Needs Review` and `Truly Unique`.
  3. Each card displays: org name, item name, type, quantity/unit, match score breakdown, suggested global matches.
  4. Action buttons: `Add to GIL`, `Match Existing`, `Reject`, `Flag alias`.
  5. After action, card collapses or moves to `Resolved`.
- Client polls `.../batches/next` for fresh batches once current batch fully resolved.

### Safety & Monitoring
- **DB protection**: read-only replica connection, pagination, configurable timeout per chunk, job aborts if average query latency exceeds threshold.
- **Error handling**: failed batches stay `pending` with `notes` describing the failure; job retries next night.
- **Logging/metrics**: counts of sensitive matches, promotions, links, rejects.
- **Auditing**: every action writes to `community_scout_candidates.resolution_payload` and existing history tables (Global Link history, UnifiedInventoryHistory).

### Implementation Tasks
1. **Schema migration**
   - Add the three tables and necessary indexes (status, classification, organization_id).
2. **Background job**
   - Implement Celery task, replica connection handling, scoring pipeline utilities, sensitivity dictionary.
3. **API blueprint**
   - Create `app/blueprints/dev/community_scout.py` with endpoints described above, permission gating, serialization helpers.
4. **UI**
   - Dev nav link + new page (likely React/Vue or server-rendered template, matching existing admin UI stack).
   - Components for batch header, candidate cards, action dialogs.
5. **Integration**
   - Hook promotion/link actions to existing services, ensure Global Link drawer triggers for affected orgs.
6. **Observability**
   - Add structured logging and metrics (StatsD / Prometheus labels).
   - Add feature flag/config toggles for batch size, thresholds, schedule.

### Open Questions / Assumptions
- Assume read replica credentials will be provided via environment variable `COMMUNITY_SCOUT_READ_DSN`.
- Assume Celery is already deployed; otherwise we can export a management command for cron.
- Translation dictionary scope: start with curated mapping for top non-English terms and expand over time.
- Moderation policy for offensive aliases: flagged entries must be reviewed before enabling the alias publicly; spec assumes dev reviewers will handle that manually via the UI toggle.
