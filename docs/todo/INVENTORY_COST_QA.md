
# BatchMate Inventory Cost Tracking QA Checklist
*Generated: 2025-05-17 00:02:02*

## 🔧 Core Data Structure

### 🟩 Inventory History Table
- [ ] Include `source` (vendor, batch, user, etc.) _(Status: Pending – `fifo_source` field exists, but vendor/user metadata not consistently filled)_

### 🟩 InventoryItem Updates
- [ ] `cost_per_unit` reflects last known purchase cost _(Status: Partial – field exists, moving-average updates still inconsistent)_
- [ ] Does NOT adjust based on spoilage _(Status: Pending – spoilage events still impact average cost calculations)_

## 🧠 Cost Calculations

### 🟨 True Cost per Unit
- [ ] Real-time calculation: `total_purchase_cost / (units_used + units_remaining)` _(Status: Partial – helper functions exist but UI/API not exposing)_
- [ ] Spoiled/trash amounts excluded from denominator _(Status: Pending – spoilage adjustments still affect moving average)_

### 🟨 Spoilage Metrics
- [ ] % of total inventory lost per ingredient _(Status: Partial – metrics available in `statistics/_inventory_stats.py`, not surfaced in UI)_
- [ ] Total spoilage cost per ingredient _(Status: Partial – calculations exist; reporting pending)_
- [ ] Monthly spoilage summary _(Status: Pending – summary endpoint not implemented)_

## 📊 Inventory Display

### 🟦 List View Enhancements
- [ ] Add column: "Effective Cost" (based on spoil-adjusted logic) _(Status: Pending – table renders only baseline cost)_
- [ ] Add column: "Spoiled This Month" _(Status: Pending – metric not shown in inventory UI)_
- [ ] Highlight in yellow if effective cost is 10–20% higher than base _(Status: Pending)_
- [ ] Highlight in red if over 20% _(Status: Pending)_

### 🟦 Tooltips & Insights
- [ ] Hover over effective cost shows loss details _(Status: Pending)_
- [ ] Hover over spoilage shows quantity details _(Status: Pending)_
- [ ] Auto-generated reorder suggestions based on usage + spoil patterns _(Status: Pending)_
