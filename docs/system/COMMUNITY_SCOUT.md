# Community Scout

## Overview
- **Purpose**: surface organization-owned inventory items that are not yet represented in the Global Inventory Library (GIL), highlight truly unique candidates versus likely matches, and drive the workflows for promoting or linking those items.
- **Actors**: internal developers (UI + API guarded by developer auth). Community data comes from every org’s `inventory_item` records where `global_item_id` is null.
- **Outcomes**:
  1. Precomputed batches (default 100 items) separate `needs_review` items from `unique` ones using alias/INCI/fuzzy scoring.
  2. Reviewer actions (“Add to global list”, “Match existing”, “Reject/flag”) call existing GIL services so downstream drawers/notifications automatically trigger.
  3. Offensive or legacy aliases are flagged for moderation prior to publication.

## Target Architecture
```
Org Inventories (read replica) ──► CommunityScoutService.generate_batches
        │                                       │
        └────────┐                              ▼
                 │                      community_scout_batch / candidate tables
                 ▼                              │
     GlobalItem catalog + aka/INCI data         ▼
     (primary read) ─────────────────► Celery/CLI job

Developer UI (flask template + ES module) ◄── REST API (`/api/dev/community-scout`)
     │                                                  │
     ├── Promote ───────────────► GlobalItem insert + GlobalLinkSuggestionService
     ├── Link existing ─────────► GlobalLinkSuggestionService (with history logging)
     ├── Reject / Flag ─────────► Candidate state transitions
     └── Fetch Next Batch ──────► marks batches `in_review`, records reviewer
```
- **Batch Generation**: off-hours Celery task or CLI (`flask community-scout-generate` / `scripts/run_community_scout.py`) pages through inventories. Heavy queries use a read replica when `COMMUNITY_SCOUT_READ_DSN` is set; otherwise falls back to the default session.
- **Data Model**:
  - `community_scout_batch`: tracks status, generation metadata, reviewer claim info.
  - `community_scout_candidate`: snapshot of each org item, classification (`needs_review` or `unique`), scoring JSON, sensitivity flags, and resolution payloads.
  - `community_scout_job_state`: single-row lock/checkpoint for the nightly sweep.

## Build & Stack
| Layer | Implementation |
| --- | --- |
| Batch job | `app/services/community_scout_service.py` + CLI (`flask community-scout-generate`) + optional `scripts/run_community_scout.py` wrapper |
| Storage | PostgreSQL tables/migration `0011_community_scout` |
| API | Blueprint `app/blueprints/api/community_scout.py` mounted at `/api/dev/community-scout` |
| UI | Developer page `app/templates/developer/community_scout.html` + ES module `app/static/js/community_scout.js`, linked from the developer dropdown |
| Auth | Developer-only guard (`current_user.user_type == 'developer'`) + Flask-Login session |
| Matching logic | Weighted signals (exact, alias, INCI, token overlap, SequenceMatcher fuzzy) plus translation dictionary and legacy-phrase flagging |
| Notifications | Accept/Link actions reuse `GlobalLinkSuggestionService` so the standard global-link drawer + `UnifiedInventoryHistory` entry fire automatically |

## Options & Configuration
- **Batch cadence**: run via Celery beat (preferred) or cron hitting `flask community-scout-generate`. Recommended nightly window when user load is low.
- **Batch sizing**: `CommunityScoutService.DEFAULT_BATCH_SIZE` (100) and `DEFAULT_PAGE_SIZE` (500) can be overridden via CLI flags or future env config.
- **Read replica**: set `COMMUNITY_SCOUT_READ_DSN` to offload heavy reads. When unset, the service uses the primary SQLAlchemy session (still paged + limited).
- **Threshold tuning**: adjust `REVIEW_SCORE_THRESHOLD`, `MIN_FUZZY_THRESHOLD`, or translation dictionaries to change classification balance.
- **Moderation**: `SENSITIVE_ALIAS_TERMS` list flags alias hits (e.g., racist historic nicknames). UI forces manual review/flagging before promotion.

## Workflow
1. **Generation**  
   - Job acquires a lock in `community_scout_job_state`, remembers `last_inventory_id_processed`, and reads unlinked inventory rows page by page.  
   - For each snapshot, it normalizes names (ASCII fold, lower, punctuation trim) and tokens + translations. Using global catalog data it calculates matches.  
   - Candidates are inserted into the current batch until `batch_size` is reached; additional matches create more batches until `max_batches` or inventory exhaustion.
2. **Review**  
   - Dev UI hits `GET /api/dev/community-scout/batches/next`, which marks the batch `in_review`, records `claimed_by_user_id`, and returns all candidates grouped by classification.  
   - The UI renders two columns (“Needs Review”, “Truly Unique”), showing organization name, scores, alias flags, and quick actions (promote, link, reject, flag).  
   - Each card now also provides an **“Open full global item form”** link that opens the standard global item creation page, prefilled with the candidate data and auto-linking back to Community Scout after save—ideal for items with extensive attributes.  
   - Each action posts to `/candidates/<id>/(promote|link|reject|flag)`. On success the card refreshes; when all candidates resolve, the batch auto-closes (`status=completed`).
3. **Global Link Trigger**  
   - Promote/link flows call `GlobalLinkSuggestionService.is_pair_compatible`, update the inventory row, and emit a `UnifiedInventoryHistory` entry.  
   - Because standard global-link logic is reused, affected orgs get the existing drawer/notification experience and future duplicates are prevented.

## Links
- Spec: `docs/system/community_scout_spec.md`
- Models: `app/models/community_scout.py`
- Service: `app/services/community_scout_service.py`
- API: `app/blueprints/api/community_scout.py`
- UI: `app/templates/developer/community_scout.html`, `app/static/js/community_scout.js`
- Migration: `migrations/versions/0011_community_scout.py`
- CLI/Script: `app/management.py (community-scout-generate)`, `scripts/run_community_scout.py`

## Testing & Validation
- **Pre-prod**: run `flask community-scout-generate --batch-size 25 --max-batches 1` against staging data to ensure candidate ingestion works without exhausting resources.
- **UI smoke test**: log in as a developer, navigate to *Developer Menu ▸ Global Library ▸ Community Scout*, click “Fetch Next Batch”, and exercise each action. Network tab should show 200 responses from `/api/dev/community-scout`.
- **Data verifications**:
  - Confirm new rows in `community_scout_batch` / `community_scout_candidate`.
  - After promoting, check `global_item` insert plus `inventory_item.global_item_id` and associated `UnifiedInventoryHistory` entry.
  - Ensure sensitive alias flags appear by seeding an org item name that matches the list.

## Operations & Maintenance
- **Monitoring**: log job metrics (counts, duration, stop reason). Consider hooking into existing stats pipeline.  
- **Cleanup**: batches and candidates can be pruned via simple retention policy (e.g., delete completed batches older than 90 days).  
- **Extensibility**: translation map and sensitive alias list live directly inside `CommunityScoutService`; future work could move them to configuration tables.  
- **Failure Recovery**: job state lock (30 min TTL) prevents concurrent scans. If the job crashes, a subsequent run reuses `last_inventory_id_processed`.  
- **Feature toggles**: none yet; add a developer feature flag if you need to hide UI/API without removing code.

## Related Documents
- `docs/system/GLOBAL_ITEM_LIBRARY.md` – canonical reference for GIL management.
- `docs/system/SERVICES.md` – service inventory (Community Scout entry added there).
- `docs/system/SYSTEM_INDEX.md` – main index with link to this document.
