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

## Billing Integration Testing

### Stripe Integration
- [ ] Subscription upgrade flow works
- [ ] Webhook processing handles all Stripe events
- [ ] Customer portal redirects correctly
- [ ] Subscription cancellation updates organization
- [ ] Billing reconciliation handles edge cases

### Container Management Testing
- [ ] Container availability checks work for recipes
- [ ] Batch container assignment and tracking
- [ ] Container adjustment logging
- [ ] Debug container endpoint security

## Alert System Testing

### Dashboard Alerts
- [ ] Alert prioritization respects user preferences
- [ ] Session-based dismissal works across requests
- [ ] Alert refresh doesn't cause infinite loops
- [ ] Cognitive load management (max alerts) works
- [ ] Timer alerts link to correct batches

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

## Testing Guidelines

### Unit Tests
```python
def test_service_respects_organization_scoping():
```

## Core Business Logic Testing

### FIFO Inventory System
- [ ] FIFO deduction maintains proper chronological order
- [ ] Lot tracking preserves complete audit trail
- [ ] Cross-model FIFO works for both ingredients and products
- [ ] Expiration date handling prevents expired inventory usage
- [ ] Partial lot consumption updates quantities correctly

## Service Architecture Validation

### Service Authority Compliance
- [ ] All inventory changes go through InventoryAdjustmentService
- [ ] All FIFO operations use FIFOService exclusively
- [ ] No direct model manipulation bypasses service layer
- [ ] Unit conversions always use UnitConversionService
- [ ] Stock checks use centralized StockCheckService

### Service Boundary Testing
- [ ] Services don't directly access other service's data
- [ ] Each service maintains single responsibility
- [ ] Service interfaces are clean and well-defined
- [ ] Cross-service communication uses proper patterns

## API Consistency Testing

### Response Format Consistency
- [ ] All API endpoints return consistent JSON structure
- [ ] Error responses follow standardized format
- [ ] Success responses include proper status codes
- [ ] Pagination follows consistent pattern across endpoints

### Error Handling Consistency
- [ ] All endpoints return proper HTTP status codes
- [ ] Error messages are user-friendly and actionable
- [ ] Validation errors include field-specific details
- [ ] System errors are logged but don't expose internals