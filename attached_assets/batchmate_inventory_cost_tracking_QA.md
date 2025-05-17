# ✅ BatchMate Inventory Optimization & Smart Cost Tracking – QA Feature Checklist
*Generated: 2025-05-16 23:55:02*

---

## 🔧 CORE DATA TRACKING STRUCTURE

### 🟩 Inventory History (InventoryHistory Table)
- [ ] Log every quantity change (purchase, spoilage, trash, use, recount)
- [ ] Include `change_type`, `quantity_change`, `unit_cost`, `timestamp`
- [ ] Support `used_for_batch_id` for traceability
- [ ] Include `source` (vendor, batch, user, etc.)

### 🟩 InventoryItem Adjustments
- [ ] `quantity` reflects actual stock
- [ ] `cost_per_unit` reflects last known purchase cost
- [ ] Does NOT adjust based on spoilage
- [ ] Supports `low_stock_threshold` for alerts

---

## 🧠 EFFECTIVE COST CALCULATIONS

### 🟨 Derived "True Cost per Unit"
- [ ] Real-time calculation:
      `total_purchase_cost / (units_used + units_remaining)`
- [ ] Spoiled/trash amounts excluded from denominator
- [ ] Do not store — always calculated dynamically

### 🟨 Spoilage Summary Metrics
- [ ] % of total inventory lost per ingredient
- [ ] Total spoilage cost per ingredient
- [ ] Monthly spoilage summary

---

## 📊 INVENTORY TABLE ENHANCEMENTS

### 🟦 Inventory List View (Table)
- [ ] Add column: “Effective Cost” (based on spoil-adjusted logic)
- [ ] Add column: “Spoiled This Month”
- [ ] Highlight in yellow if effective cost is 10–20% higher than base
- [ ] Highlight in red if over 20%

### 🟦 Tooltips & Insights
- [ ] Hover over effective cost badge shows:
      “Includes loss from 3 expired restocks”
- [ ] Hover over spoilage badge shows:
      “180 mL trashed this month”

---

## 🧠 SMART ALERTS (NEURODIVERGENT-FRIENDLY)

### 🟧 Loss Feedback Alerts
- [ ] If spoilage > threshold (e.g., 10%), show soft alert:
      “Consider ordering less. Spoilage is up this month.”
- [ ] Alert only appears once per item until acknowledged

### 🟧 Cost Creep Alerts
- [ ] If effective cost exceeds purchase cost by >15%:
      Show: “Your cost per jar is being inflated by loss.”

### 🟧 No Shaming, Just Support
- [ ] Alerts written with supportive, positive phrasing
- [ ] Never punish the user — guide them gently

---

## 🧭 FUTURE FEATURE ZONE

### 🌀 Business Center (Later)
- [ ] Roll-up view: “Top 5 costly ingredients (after loss)”
- [ ] Price recommendations
- [ ] Supplier cost comparisons
- [ ] Auto-generated reorder suggestions based on usage + spoil

