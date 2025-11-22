
# Inventory FIFO Upgrade QA Checklist

## 1. Database Structure
- [ ] Add timestamp and source tracking (purchase, production, adjustment) _(Status: Partial – timestamps in place, source metadata still sparse)_

## 2. Raw Ingredient FIFO
- [ ] Add vendor/source tracking _(Status: Partial – lot `source_type` stored but vendor linkage TBD)_
- [ ] Test multi-purchase scenarios _(Status: Pending – automated tests missing)_

## 3. Intermediate Ingredient FIFO
- [ ] Remove remaining_quantity from Batch model _(Status: Pending – `Batch.remaining_quantity` still defined)_
- [ ] Test mixed-source deductions _(Status: Pending – needs coverage)_

## 4. UI/UX Implementation
- [ ] Add purchase history view _(Status: Pending – UI does not surface historical purchases)_
- [ ] Create inventory adjustment interface _(Status: Pending – adjustments still admin-only forms)_
- [ ] Add cost tracking display _(Status: Pending – UI lacks effective cost column)_
- [ ] Test mobile responsiveness _(Status: Pending – no responsive QA)_

## 5. Integration Points
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
