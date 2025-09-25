# PlanSnapshot (Immutable Batch Plan)

This document delineates the PlanSnapshot DTO end‑to‑end. The snapshot is the single source of truth for starting a batch and protecting in‑progress batches from recipe edits.

## Purpose
- Freeze all inputs required to start a batch (portions, yield, scaled lines, containers).
- Persist verbatim at batch start in `batch.plan_snapshot` for read‑only displays and auditing.
- Ensure deductions and batch rows match the snapshot quantities.

## Schema (conceptual)
```json
{
  "recipe_id": 12,
  "scale": 1.0,
  "batch_type": "product",
  "projected_yield": 10.0,
  "projected_yield_unit": "oz",
  "portioning": {
    "is_portioned": true,
    "portion_name": "bars",
    "portion_unit_id": 120,
    "portion_count": 20
  },
  "containers": [
    { "id": 11, "quantity": 4 }
  ],
  "ingredients_plan": [
    { "inventory_item_id": 42, "quantity": 2.0, "unit": "count" }
  ],
  "consumables_plan": [
    { "inventory_item_id": 77, "quantity": 1.0, "unit": "count" }
  ],
  "category_extension": {
    "soap": { "lye_ratio": 0.28 }
  }
}
```

## Field Definitions
- recipe_id: Integer. The recipe used to build the plan.
- scale: Float. Scale factor applied when generating projected yield and scaling lines.
- batch_type: String. "ingredient" or "product".
- projected_yield / projected_yield_unit: Frozen values used for batch.projected_yield/unit.
- portioning (always present):
  - is_portioned: Boolean. If false, other portion fields may be null.
  - portion_name: String | null. User‑defined count unit name (e.g., "bars").
  - portion_unit_id: Integer | null. Unit ID for the portion name (when defined as a Unit).
  - portion_count: Integer | null. Planned portions for the batch scale.
- containers: Array of selections; immutable planned container usage (id, quantity).
- ingredients_plan / consumables_plan: Scaled lines (recipe × scale); the quantities the batch will deduct at start.
- category_extension: Optional, namespaced JSON for category‑specific fields (e.g., lye ratios, steep times, wick lengths).

## Lifecycle
1) Build during Production Planning (server‑side):
   - `PlanProductionService.build_plan(recipe, scale, batch_type, notes?, containers?)`
   - Scales recipe lines, freezes projected yield/unit, merges portioning from recipe’s additive fields, freezes container selections.

2) Submit to Start Batch (client → API):
   - `POST /batches/api/start-batch` with `{ plan_snapshot: PlanSnapshot }`.
   - API validates and forwards snapshot to `BatchOperationsService.start_batch(plan_snapshot)`.

3) Start Batch (service):
   - Persists `batch.projected_yield`, `batch.projected_yield_unit`, portion fields, and `batch.plan_snapshot` verbatim.
   - Performs unit conversion + inventory deductions using the same scaled quantities (matching snapshot).
   - Creates `BatchIngredient`, `BatchConsumable`, and `BatchContainer` rows consistent with the snapshot.
   - Any error → rollback; no partial starts.

4) In‑Progress and Record Views:
   - Planned (read‑only): read from `batch.plan_snapshot` (ingredients_plan, consumables_plan, containers, portioning, projected yield/unit).
   - Actual: read from batch rows (ingredients/consumables/containers) and extras added after start.
   - Notes are edited post‑start via a separate endpoint and are not part of the snapshot.

## Mapping to Batch
- batch.projected_yield ← snapshot.projected_yield
- batch.projected_yield_unit ← snapshot.projected_yield_unit
- batch.is_portioned / portion_name / projected_portions ← snapshot.portioning
- batch.plan_snapshot ← snapshot (verbatim)
- BatchIngredient/BatchConsumable rows reflect snapshot scaled quantities (after conversions and deductions)
- BatchContainer rows reflect snapshot containers selections

## Guarantees
- Immutability: Snapshot never changes after start.
- Protection: Changing a recipe later does not affect an in‑progress batch’s planned view.
- Consistency: Deductions and batch rows match snapshot quantities.

## Validation & Errors
- API rejects missing/invalid `plan_snapshot` (400) and surfaces start errors (deduction failures).
- Service rolls back on error; no partial inventory changes.

## Future Extensions
- Add a JSON Schema for PlanSnapshot validation.
- Version field inside the snapshot for forward compatibility of category_extension.