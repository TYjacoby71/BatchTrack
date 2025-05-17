
# BatchMate Inventory Cost Tracking QA Checklist
*Generated: 2025-05-17 00:02:02*

## 🔧 Core Data Structure

### 🟩 Inventory History Table
- [ ] Log every quantity change (purchase, spoilage, trash, use, recount)
- [ ] Include `change_type`, `quantity_change`, `unit_cost`, `timestamp`
- [ ] Support `used_for_batch_id` for traceability
- [ ] Include `source` (vendor, batch, user, etc.)

### 🟩 InventoryItem Updates
- [ ] `quantity` reflects actual stock
- [ ] `cost_per_unit` reflects last known purchase cost
- [ ] Does NOT adjust based on spoilage
- [ ] Supports `low_stock_threshold` for alerts

## 🧠 Cost Calculations

### 🟨 True Cost per Unit
- [ ] Real-time calculation: `total_purchase_cost / (units_used + units_remaining)`
- [ ] Spoiled/trash amounts excluded from denominator
- [ ] Do not store — always calculated dynamically

### 🟨 Spoilage Metrics
- [ ] % of total inventory lost per ingredient
- [ ] Total spoilage cost per ingredient
- [ ] Monthly spoilage summary

## 📊 Inventory Display

### 🟦 List View Enhancements
- [ ] Add column: "Effective Cost" (based on spoil-adjusted logic)
- [ ] Add column: "Spoiled This Month"
- [ ] Highlight in yellow if effective cost is 10–20% higher than base
- [ ] Highlight in red if over 20%

### 🟦 Tooltips & Insights
- [ ] Hover over effective cost shows loss details
- [ ] Hover over spoilage shows quantity details
- [ ] Auto-generated reorder suggestions based on usage + spoil patterns
