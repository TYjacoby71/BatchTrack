
# BatchTrack MVP Bug & QA Checklist

## 1. UNIVERSAL STOCK CHECK SERVICE (USCS)
- [ ] Global `/api/check-stock` endpoint implementation working
- [ ] Unified API response format with type, name, needed, available, status
- [ ] Unit conversion integration verified
- [ ] Status indicators (OK/LOW/NEEDED) accuracy verified
- [ ] Stock check button behavior working
- [ ] Bulk stock check export working

## 2. UNIT CONVERSION SYSTEM
- [ ] Base unit and multiplier relationships clear
- [ ] Custom unit creation process working
- [ ] Unit conversion path through base units consistent
- [ ] Custom mappings saving correctly
- [ ] Unit deletion handling properly
- [ ] Unit conversion edge cases handled

## 3. CONTAINER MANAGEMENT
- [ ] Container validation uniqueness working
- [ ] Container names follow naming convention (see CONTAINER_NAMING.md)
- [ ] Container capacities clearly indicated in names
- [ ] Available containers display accurate
- [ ] Auto-fill container logic verified
- [ ] Container type filtering functional
- [ ] Container cost tracking working
- [ ] Container inventory sync verified

## 4. INVENTORY TRACKING
- [ ] FIFO inventory tracking working
- [ ] Expiration alerts displaying correctly
- [ ] Low stock alerts accurate
- [ ] Inventory adjustments logging properly
- [ ] Stock level thresholds working
- [ ] Inventory export/import functioning
- [ ] Batch remaining quantity tracking accurate
- [ ] Batch inventory log entries recording correctly
- [ ] FIFO deduction from oldest batches verified
- [ ] Intermediate ingredient FIFO consumption working
- [ ] Product FIFO consumption working

## 5. BATCH PRODUCTION FLOW
- [ ] Scale selection interface working
- [ ] Container selection following scale input
- [ ] Batch status tracking accurate
- [ ] Actual yield recording working
- [ ] Batch completion flow verified
- [ ] Production planning interface clear
- [ ] Remaining quantity display accurate in batch list
- [ ] Batch inventory adjustments logged properly
- [ ] Intermediate ingredient consumption tracked
- [ ] Batch expiration tracking working

## PRIORITY ORDER
1. 🔴 FIFO Implementation
2. 🔴 Batch Inventory Tracking
3. 🟡 Unit Conversion System
4. 🟡 Stock Check Service
5. 🟢 Container Management

## Current Issues
1. Unit conversion edge cases need testing
2. Container validation needs improvement
3. Stock check service needs centralization
4. Mobile interface needs optimization
5. Production planning UX needs refinement
6. FIFO deduction validation required
7. Batch inventory log display needed
8. Remaining quantity calculation verification needed
