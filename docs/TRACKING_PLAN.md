# Tracking Plan

This plan defines domain events emitted by the app, their properties, and how they map to analytics metrics and warehouse models.

## Events

1) inventory_adjusted
- When: Any inventory adjustment via canonical delegator
- Entity: inventory_item
- Properties:
  - change_type: string (restock, finished_batch, batch, spoil, expired, trash, damaged, sale, recount, returned, refunded, release_reservation)
  - quantity_delta: float (positive for adds, negative for deductions)
  - unit: string
  - notes: string
  - cost_override: float|null
  - original_quantity: float
  - new_quantity: float
  - item_name: string
  - item_type: string (ingredient, container, product)
  - batch_id: int|null
  - is_initial_stock: bool

2) batch_started
- When: After batch creation and deductions commit
- Entity: batch
- Properties:
  - recipe_id: int
  - scale: float
  - batch_type: string (ingredient|product)
  - projected_yield: float
  - projected_yield_unit: string
  - label_code: string

3) batch_completed
- When: After batch completion commit
- Entity: batch
- Properties:
  - label_code: string
  - final_quantity: float
  - output_unit: string
  - completed_at: ISO8601 string

4) batch_cancelled
- When: After batch cancellation and restoration commit
- Entity: batch
- Properties:
  - label_code: string
  - restoration_summary: array of strings

5) timer_started
- When: After `TimerService.create_timer`
- Entity: timer
- Properties:
  - batch_id: int
  - duration_seconds: int
  - description: string

6) timer_stopped
- When: After `TimerService.stop_timer`
- Entity: timer
- Properties:
  - batch_id: int
  - duration_seconds: int

## Warehouse modeling

- Raw table: `domain_event` (already persisted by the app)
- Staging (dbt): `stg_events` normalizes event_name, timestamps, tenant and user context
- Facts:
  - fct_inventory_movement: from inventory_adjusted events (signed quantity, cost)
  - fct_batch: from batch_started/completed/cancelled and joins to batch tables
  - fct_timer: from timer_started/stopped deriving durations

## Core metrics

- Inventory usage: sum(quantity_delta) where change_type in ('batch','use','sale','tester','sample','gift') and entity_type='inventory_item'
- Spoilage cost: sum(cost) where change_type in ('spoil','expired','damaged','trash')
- Total cost held: latest inventory valuation from application tables; events provide changes
- Batch time: p50/p90 from `fct_timer` grouped by batch_id
- Batch cost average: avg(total_actual_cost) from `BatchStats` combined with events for coverage
- Freshness score: derived from lot age in application tables; events carry item_age context if extended later
- Overbuying index: days_of_stock vs target; compute with rolling usage from events or existing history

## Governance

- All events carry `organization_id` and `user_id` when available. Aggregate across orgs only with strict thresholds.
- Version schemas using `schema_version` per event; this plan is v1.

## Backfill

- Backfill scripts should read from `UnifiedInventoryHistory` and `Batch` to create historical `DomainEvent` rows for key events (inventory_adjusted, batch_completed, etc.).
