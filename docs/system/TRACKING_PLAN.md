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

## Relevance Check (2026-02-17)
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
