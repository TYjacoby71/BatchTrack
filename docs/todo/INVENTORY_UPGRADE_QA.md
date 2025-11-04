
# Inventory FIFO Upgrade QA Checklist

## 1. Database Structure
- [ ] Create InventoryHistory table for tracking changes
- [ ] Add fields: id, inventory_item_id, change_type, quantity, unit
- [ ] Add timestamp and source tracking (purchase, production, adjustment)
- [ ] Add cost tracking fields for price history
- [ ] Verify foreign key relationships

## 2. Raw Ingredient FIFO
- [ ] Implement purchase event tracking
- [ ] Add vendor/source tracking
- [ ] Track cost per purchase
- [ ] Implement FIFO deduction logic
- [ ] Test multi-purchase scenarios
- [ ] Verify unit consistency

## 3. Intermediate Ingredient FIFO
- [ ] Remove remaining_quantity from Batch model
- [ ] Update batch completion to create inventory records
- [ ] Implement FIFO deduction from batches
- [ ] Test mixed-source deductions
- [ ] Verify batch traceability

## 4. UI/UX Implementation
- [ ] Add purchase history view
- [ ] Create inventory adjustment interface
- [ ] Implement FIFO transaction log
- [ ] Add cost tracking display
- [ ] Create inventory alerts for low stock
- [ ] Test mobile responsiveness

## 5. Integration Points
- [ ] Update stock check service
- [ ] Modify batch deduction system
- [ ] Update inventory adjustment routes
- [ ] Integrate with unit conversion
- [ ] Test recipe scaling impact

## 6. Migration Process
- [ ] Create data migration plan
- [ ] Back up existing inventory data
- [ ] Test migration rollback
- [ ] Verify data integrity
- [ ] Update dependent services

## 7. Testing Scenarios
- [ ] Multi-batch deduction
- [ ] Mixed unit conversions
- [ ] Cost averaging calculations
- [ ] Concurrent transactions
- [ ] Edge case handling

## Priority Order
1. 🔴 Database structure implementation
2. 🔴 Raw ingredient FIFO tracking
3. 🟡 Intermediate ingredient integration
4. 🟡 UI/UX updates
5. 🟢 Migration execution
6. 🟢 Integration testing

## Current Status
- Database schema planned
- Basic FIFO service implemented
- UI requirements identified
- Migration strategy outlined
