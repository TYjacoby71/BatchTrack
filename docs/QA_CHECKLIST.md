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

See detailed Unit & Mapping QA guidelines in [UNIT_MAPPING_QA.md](UNIT_MAPPING_QA.md)

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

## 5. BATCH PRODUCTION FLOW
- [ ] Scale selection interface working
- [ ] Container selection following scale input
- [ ] Batch status tracking accurate
- [ ] Actual yield recording working
- [ ] Batch completion flow verified
- [ ] Production planning interface clear

## PRIORITY ORDER
1. 🔴 Unit Conversion System
2. 🔴 Stock Check Service
3. 🟡 Container Management
4. 🟡 Inventory Tracking
5. 🟢 Batch Production Flow

## Current Issues
1. Unit conversion edge cases need testing
2. Container validation needs improvement
3. Stock check service needs centralization 
4. Mobile interface needs optimization
5. Production planning UX needs refinement