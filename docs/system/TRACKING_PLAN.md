# Tracking Plan

## Synopsis
This document defines the current domain-event tracking layer used for analytics and outbox delivery. Events are written to `domain_event` and can be dispatched asynchronously to downstream webhooks.

## Glossary
- **DomainEvent**: Persisted event envelope row in `domain_event`.
- **Emitter**: `EventEmitter` helper that writes domain events.
- **Dispatcher**: Background process that delivers unprocessed outbox events.

## Event Transport Architecture

1. Application/services emit events via `EventEmitter.emit(...)`.
2. Events persist to `domain_event` with context and JSON properties.
3. Dispatcher command processes pending rows:
   - `flask dispatch-domain-events`
4. Downstream consumers read webhook payloads or analytics tables.

## Event Envelope (Current)
Core fields on every event record:
- `event_name`
- `occurred_at`
- `organization_id`
- `user_id`
- `entity_type`
- `entity_id`
- `correlation_id`
- `source`
- `schema_version`
- `properties` (JSON)
- outbox status fields (`is_processed`, `processed_at`, `delivery_attempts`)

## Currently Emitted Event Families

### Inventory
- `inventory_adjusted`
  - source: inventory adjustment core delegator

### Batch lifecycle
- `batch_started`
- `batch_completed`
- `batch_cancelled`
- `batch_failed`

### Timer lifecycle
- `timer_started`
- `timer_stopped`

### Recipe lifecycle
- `recipe_created`
- `recipe_updated`
- `recipe_deleted`

### Product lifecycle
- `product_created`
- `product_variant_created`
- `sku_created`

### Stats/analytics internals
- `batch_metrics_computed`

## Analytics Mapping Guidance
- Keep `event_name` stable for downstream models.
- Prefer additive property fields over destructive schema changes.
- Use `schema_version` for explicit payload evolution.
- Scope analytics queries by `organization_id` for tenant isolation.

## External Website/Product Analytics
BatchTrack supports optional client-side analytics snippets in the shared layout:

- **GA4** via `GOOGLE_ANALYTICS_MEASUREMENT_ID`
  - Best for acquisition/SEO/marketing attribution.
  - Captures website traffic trends and campaign performance.
- **PostHog** via `POSTHOG_PROJECT_API_KEY`
  - Best for product analytics and behavioral funnels.
  - Captures pageviews/pageleave events and can be extended to feature-level events.

Recommended baseline:
1. Use **GA4** for top-of-funnel traffic and ad attribution.
2. Use **PostHog** for in-app behavior and retention analysis.
3. Keep domain events as the backend source of truth for tenant-scoped operational analytics.

### Config keys
- `GOOGLE_ANALYTICS_MEASUREMENT_ID` (e.g., `G-XXXXXXXXXX`)
- `POSTHOG_PROJECT_API_KEY`
- `POSTHOG_HOST` (defaults to `https://us.i.posthog.com`)
- `POSTHOG_CAPTURE_PAGEVIEW` (default `true`)
- `POSTHOG_CAPTURE_PAGELEAVE` (default `true`)

## Relevance Check (2026-02-18)
Validated against:
- `app/models/domain_event.py`
- `app/services/event_emitter.py`
- `app/services/domain_event_dispatcher.py`
- `app/scripts/commands/maintenance.py`
- `app/services/inventory_adjustment/_core.py`
- `app/services/batch_service/batch_operations.py`
- `app/services/timer_service.py`
- `app/services/recipe_service/_core.py`
- `app/services/product_service.py`
- `app/config_schema_parts/operations.py`
- `app/config.py`
- `app/templates/layout.html`
