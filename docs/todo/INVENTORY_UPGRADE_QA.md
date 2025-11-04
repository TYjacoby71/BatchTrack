
# Inventory FIFO Upgrade QA Checklist

## 1. Database Structure
- [x] Create InventoryHistory table for tracking changes _(Status: Complete – `inventory_history` & `unified_inventory_history` tables live)_
- [x] Add fields: id, inventory_item_id, change_type, quantity, unit _(Status: Complete – schema columns present)_
- [x] Add timestamp and source tracking (purchase, production, adjustment) _(Status: Partial – timestamps in place, source metadata still sparse)_
- [x] Add cost tracking fields for price history _(Status: Complete – `unit_cost`, `valuation_method`)_
- [x] Verify foreign key relationships _(Status: Complete – FK constraints enforced in models/migrations)_

## 2. Raw Ingredient FIFO
- [x] Implement purchase event tracking _(Status: Complete – inventory adjustments create FIFO lots & history)_
- [ ] Add vendor/source tracking _(Status: Partial – lot `source_type` stored but vendor linkage TBD)_
- [x] Track cost per purchase _(Status: Complete – `unit_cost` captured on lots & history)_
- [x] Implement FIFO deduction logic _(Status: Complete – `inventory_adjustment/_fifo_ops.py` in use)_
- [ ] Test multi-purchase scenarios _(Status: Pending – automated tests missing)_
- [x] Verify unit consistency _(Status: Complete – conversions applied during deductions)_

## 3. Intermediate Ingredient FIFO
- [ ] Remove remaining_quantity from Batch model _(Status: Pending – `Batch.remaining_quantity` still defined)_
- [x] Update batch completion to create inventory records _(Status: Complete – batch finish writes inventory events)_
- [x] Implement FIFO deduction from batches _(Status: Complete – batch finish leverages FIFO services)_
- [ ] Test mixed-source deductions _(Status: Pending – needs coverage)_
- [x] Verify batch traceability _(Status: Complete – events cross-link via `batch_id` and `fifo_code`)_

## 4. UI/UX Implementation
- [ ] Add purchase history view _(Status: Pending – UI does not surface historical purchases)_
- [ ] Create inventory adjustment interface _(Status: Pending – adjustments still admin-only forms)_
- [x] Implement FIFO transaction log _(Status: Complete – inventory history table + drawer views available)_
- [ ] Add cost tracking display _(Status: Pending – UI lacks effective cost column)_
- [x] Create inventory alerts for low stock _(Status: Complete – low stock alerts derived from thresholds)_
- [ ] Test mobile responsiveness _(Status: Pending – no responsive QA)_

## 5. Integration Points
- [x] Update stock check service _(Status: Complete – stock check references FIFO lots)_
- [x] Modify batch deduction system _(Status: Complete – batch services rely on FIFO)_
- [x] Update inventory adjustment routes _(Status: Complete – routes call adjustment services)_
- [x] Integrate with unit conversion _(Status: Complete – conversions enforced during adjustments)_
- [ ] Test recipe scaling impact _(Status: Pending – requires scenario coverage)_

## 6. Migration Process
- [ ] Create data migration plan _(Status: Pending – documentation not committed)_
- [ ] Back up existing inventory data _(Status: Pending – runbook missing)_
- [ ] Test migration rollback _(Status: Pending)_
- [ ] Verify data integrity _(Status: Pending – validation scripts needed)_
- [ ] Update dependent services _(Status: Pending – audit incomplete)_

## 7. Testing Scenarios
- [ ] Multi-batch deduction _(Status: Pending – add integration tests)_
- [ ] Mixed unit conversions _(Status: Pending)_
- [ ] Cost averaging calculations _(Status: Pending)_
- [ ] Concurrent transactions _(Status: Pending)_
- [ ] Edge case handling _(Status: Pending)_

## Priority Order
1. 🔴 Database structure implementation
2. 🔴 Raw ingredient FIFO tracking
3. 🟡 Intermediate ingredient integration
4. 🟡 UI/UX updates
5. 🟢 Migration execution
6. 🟢 Integration testing

## Current Status
- Database schema implemented; metadata gaps remain for vendor/source attribution
- FIFO services live in production code; mixed-source edge cases lack automated tests
- UI enhancements (effective cost, purchase history) outstanding
- Migration + regression test plans still need to be authored
