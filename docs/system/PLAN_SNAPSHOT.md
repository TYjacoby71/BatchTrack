# PlanSnapshot (Batch Start Authority)

## Synopsis
`PlanSnapshot` is the immutable payload that defines what a batch starts with: scaled lines, yield projection, portioning, container selections, and category-specific extension data. It is built server-side and persisted to `batch.plan_snapshot` when batch start succeeds.

## Glossary
- **PlanSnapshot**: Frozen batch-start payload (`app/services/production_planning/types.py`).
- **Category extension**: Structured category-specific JSON copied from recipe context.
- **Planned vs actual**: Snapshot intent versus post-start batch row changes (including extras).

## Canonical Shape (Current)

Core fields in `PlanSnapshot` include:
- `recipe_id`
- `lineage_snapshot`
- `scale`
- `batch_type`
- `notes`
- `projected_yield`
- `projected_yield_unit`
- `portioning` (`is_portioned`, `portion_name`, `portion_unit_id`, `portion_count`)
- `ingredients_plan[]` (`inventory_item_id`, `quantity`, `unit`)
- `consumables_plan[]` (`inventory_item_id`, `quantity`, `unit`)
- `containers[]` (`id`, `quantity`)
- `requires_containers`
- `category_extension`

## Lifecycle
1. **Build snapshot**  
   `PlanProductionService.build_plan(recipe, scale, batch_type, notes, containers)`

2. **Submit start request**  
   `POST /batches/api/start-batch` (or start route variant) passes snapshot payload.

3. **Start batch transaction**  
   `BatchOperationsService.start_batch(plan_snapshot)`:
   - writes projected fields and snapshot onto `Batch`
   - performs deductions
   - creates batch line rows
   - emits start event on success

4. **View semantics**
   - Planned values: read from `batch.plan_snapshot`.
   - Actual values: read from `BatchIngredient`/`BatchConsumable`/`BatchContainer` and extras.

## Guarantees
- Snapshot is persisted only when start succeeds.
- Start is transactional: deduction/row failures rollback.
- Recipe edits after batch start do not mutate stored snapshot intent.

## Notes on Extended Payload Keys
Batch start logic also tolerates optional operational keys (for example skip lists or forced-start summaries) when provided by upstream flows.

## Relevance Check (2026-02-17)
Validated against:
- `app/services/production_planning/types.py`
- `app/services/production_planning/service.py`
- `app/services/batch_service/batch_operations.py`
- `app/blueprints/batches/routes.py`
- `app/models/batch.py` (`plan_snapshot` + computed projection columns)