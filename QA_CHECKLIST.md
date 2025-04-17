
# BatchTrack MVP Bug & QA Checklist

## 1. ROUTE & TEMPLATE VERIFICATION

**Dashboard**
- [ ] /dashboard route loads with modal functionality
- [ ] Inventory alert card present for low stock
- [ ] All navigation buttons functional

**Recipes**
- [x] Parent/Variation grouping displays correctly
- [x] "Create Variation" duplicates parent + allows editing
- [x] Variation dropdown on plan production
- [x] "Clone Recipe" works on both parent and variations

**Batches**
- [x] Shows batch status (in_progress, complete)
- [x] Start/Finish buttons reflect batch state
- [x] Timers block batch completion if active

**Inventory**
- [x] Category filtering implemented
- [x] "Ingredient" renamed to "Inventory"

## 2. BATCH START FLOW

**Modal Components**
- [x] Recipe parent selection
- [x] Variation dropdown when applicable
- [x] Scale input
- [x] Container selector
- [x] Stock check functionality

**Container Logic** 
- [x] Deducts from inventory on batch start
- [ ] Unit type handling needs verification

## 3. TIMERS

- [x] Multiple timer support
- [x] Timer display
- [x] Blocks batch completion
- [ ] Override for "Cure" timers needed

## 4. DATABASE

- [x] batch.status column implemented
- [x] product_variation table linked
- [x] inventory_item types supported
- [x] timer storage implemented

## 5. MODAL + DYNAMIC LOGIC

- [x] Quick Add features working
- [ ] Mobile UX optimization needed
- [ ] ND-friendly flow verification needed

## 6. SETTINGS PAGE

- [ ] Route needs implementation
- [ ] Unit definition management
- [ ] Category management

## 7. PERFORMANCE + UI

- [ ] Mobile display testing needed
- [ ] Console error check needed
- [ ] Modal transition review
- [ ] Input persistence verification

## Current Issues

1. Dashboard route appears to be using 'home.homepage' instead of '/dashboard'
2. Settings page functionality is not implemented
3. Mobile optimization needs review
4. Timer override for "Cure" type not implemented
5. Unit type edge cases need verification
