
# PR2 Inventory Call Sites Analysis

## Goal
Map every place inventory is adjusted or FIFO math is called to ensure canonicalization through `app/services/inventory_adjustment.py`.

## Current Canonical Service
✅ **Primary Entry Point**: `app/services/inventory_adjustment.py::process_inventory_adjustment()`
- This function is already positioned as the canonical entry point
- Contains comprehensive FIFO logic, validation, and audit trails
- Has backwards compatibility shims

## Call Site Analysis

### 1. Direct Canonical Service Usage (✅ VERIFIED 2025‑11‑22)
- `app/blueprints/batches/finish_batch.py`, `add_extra.py`, `start_batch.py`, and `cancel_batch.py` all import `process_inventory_adjustment()` directly. No blueprint-level `FIFOService` imports remain.
- Canonical logic continues to live in `app/services/inventory_adjustment.py::process_inventory_adjustment()`.

### 2. Legacy Compatibility Layer (🟡 STILL PRESENT)
- `app/services/inventory_adjustment.py::InventoryAdjustmentService` remains as a shim for legacy imports. Delete after confirming no third-party integrations rely on it.
- `app/blueprints/fifo/__init__.py` now only exposes stub functions that raise `NotImplementedError`, acting as a safety net for stray imports.

### 3. Internal FIFO Operations (✅ INTERNAL ONLY)
- The internal `_FIFOService` helpers invoked by the canonical service stay encapsulated; nothing in `app/blueprints/**` references them directly.

### 4. Regression Watchlist (🔍)
- Keep grep-based smoke tests to ensure no new direct FIFO calls appear in routes, templates, or JavaScript.
- Confirm API endpoints hit by JS continue to delegate to `process_inventory_adjustment()`.

## Current Grep Snapshot

- `rg -n "FIFOService" app/blueprints` → **no matches**.
- `rg -n "FIFOService" app/services` → only hits test stubs in `app/services/pos_integration.py`.
- `rg -n "process_inventory_adjustment" app/blueprints/batches` → confirms every batch flow calls the canonical service.

## Analysis Summary

- ✅ Batch flows are fully aligned to the canonical entry point.
- 🟡 Compatibility shims exist solely for import safety and can be removed later.
- 🔍 Ongoing monitoring is required so no new shortcuts creep back in.

## Next Steps for PR2
1. ✅ Confirmed zero `FIFOService` imports inside blueprints as of 2025‑11‑22.
2. [ ] Remove `InventoryAdjustmentService` and FIFO stub exports after telemetry shows no external callers.
3. [ ] Add route → service wiring tests to prevent regressions.
4. [ ] Automate the grep checks (pre-commit or CI) so canonicalization stays enforced.
