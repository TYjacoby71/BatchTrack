
# Immediate Fix List - Current Bugs & Issues

**🚨 Fix these issues immediately for stable operation**

## 🔥 **CRITICAL BUGS** (Fix Today)

### **API Response Inconsistency**
- **Status:** 🔄 In Progress – numerous API routes still return HTML or redirect responses (e.g., `app/blueprints/recipes/routes.py` quick actions)
- **Issue**: Mixed HTML redirects and JSON responses across endpoints
- **Impact**: Frontend JavaScript expects JSON, gets HTML redirects
- **Fix**: Standardize all API endpoints to return consistent JSON responses
- **Priority**: HIGH - affects user experience

### **Service Architecture Violations**
- **Status:** 🔄 In Progress – direct model access persists in UI blueprints (e.g., `recipes/routes.py`, `inventory/routes.py`)
- **Issue**: Some routes bypass service layer authority
- **Risk**: Data inconsistency and inventory sync issues
- **Fix**: Audit all routes to ensure service layer compliance
- **Examples**: Direct model queries instead of using services

## 🟡 **HIGH PRIORITY FIXES** (This Week)

### **Unit Conversion Edge Cases**
- **Status:** 🔄 In Progress – core mapping flags exist (`Unit.is_mapped`), but guardrails in `conversion/routes.py` still allow inconsistent states
- **Issue**: Custom unit creation causes confusion with base units
- **Fix**: Clarify Unit table vs CustomUnitMapping relationship
- **Impact**: Recipe scaling and inventory calculations

### **Quick Add Form Issues**
- **Status:** ⏳ Pending – `/recipes/ingredients/quick-add` still posts full-page and resets form state
- **Issue**: Page reload loses edit state, unit selection resets
- **Fix**: Convert to AJAX response, maintain form state
- **File**: `app/blueprints/quick_add/routes.py`

### **Container Selection Logic**
- **Status:** ⏳ Pending – container availability logic remains unchanged in `app/services/inventory_adjustment`
- **Issue**: Container validation and auto-fill needs improvement
- **Fix**: Update container availability display and validation
- **Impact**: Batch planning user experience

### **Micro Transaction Slip**
- **Status:** ⏳ Pending – no minimum thresholds enforced; see `inventory_adjustment/_validation.py`
- **Issue**: Tiny inventory adjustments go unnoticed or create 0-change entries
- **Fix**: Add minimum threshold validation and wrapper confirmation
- **Risk**: Inventory desync over time

### **Failed Add Messages**
- **Status:** ⏳ Pending – unit conversion failures still return generic errors from `inventory_adjustment` services
- **Issue**: Unit conversion failures show generic "failed" with no details
- **Fix**: Provide specific error messages for unit mapping issues
- **UX**: User doesn't know why ingredient addition failed

## 🟢 **MEDIUM PRIORITY FIXES** (Next Sprint)

### **FIFO/Inventory Sync Risk**
- **Status:** 🔄 In Progress – validation helpers exist but are not enforced pre-commit in all flows
- **Issue**: No validation wrapper for inventory adjustment events
- **Fix**: Add sync confirmation after all adjustment operations
- **Prevention**: Detect and prevent inventory/FIFO desync

### **Edit Ingredient Form State**
- **Status:** ⏳ Pending – recipe edit templates still reload without retaining selection
- **Issue**: Unit selection resets after page reload
- **Fix**: Persist form state through edit operations
- **File**: `app/templates/recipes/edit_ingredient.html`

### **Expiration Date Tracking**
- **Status:** 🔄 In Progress – expiration data captured in `InventoryLot`, but batch completion still defaults timestamp
- **Issue**: Intermediate batches get generic timestamps, not actual production dates
- **Fix**: Use actual batch completion time for expiration calculations
- **Impact**: Accurate shelf-life tracking

### **Permission System Inconsistencies**
- **Status:** ⏳ Pending – hardcoded checks still present in older blueprints (e.g., `app/blueprints/admin/routes.py`)
- **Issue**: Some routes use hardcoded permission checks
- **Fix**: Standardize to use `has_permission(user, permission_name)` everywhere
- **Scope**: All blueprint routes

## 🔧 **TECHNICAL DEBT** (Ongoing)

### **Blueprint Organization**
- **Status:** ⏳ Pending – route/service separation inconsistent across existing blueprints
- **Issue**: Mixed responsibilities, duplicate logic across blueprints
- **Cleanup**: Separate UI and API concerns cleanly
- **Goal**: Single responsibility per blueprint

### **Template Logic Leakage**
- **Status:** ⏳ Pending – templates still contain calculation logic (e.g., `templates/pages/batches/batches_list.html`)
- **Issue**: Business logic embedded in templates
- **Fix**: Move calculations to service layer
- **Maintainability**: Easier testing and modification

### **Error Handling Standardization**
- **Status:** 🔄 In Progress – shared drawer patterns improving, but API error payloads not standardized
- **Issue**: Inconsistent error message formats
- **Fix**: Create standardized error response middleware
- **Benefits**: Better debugging and user experience

## 📋 **IMMEDIATE ACTION ITEMS**

### **Today's Fixes**
- 1. ✅ Complete dashboard alerts JavaScript function
- 2. 🔄 Audit API endpoints for response consistency (open)
- 3. 🔄 Add validation wrapper to inventory adjustment routes (open)
- 4. ⏳ Fix quick add form to use AJAX responses (open)

### **This Week's Priorities**
1. Standardize all API endpoint responses to JSON
2. Complete unit conversion edge case handling
3. Add specific error messages for failed operations
4. Implement inventory/FIFO sync validation

### **Testing Requirements**
- [ ] Test all fixed endpoints for consistent responses
- [ ] Verify service layer compliance in all routes
- [ ] Validate error message clarity for users
- [ ] Test form state preservation after fixes

## 🎯 **SUCCESS METRICS**

### **Bug Resolution Targets**
- Zero critical JavaScript errors in console
- All API endpoints return consistent JSON format
- No service layer authority bypassing
- Clear error messages for all failure scenarios

### **Code Quality Goals**
- Service layer compliance: 100%
- API response consistency: 100%
- Error message clarity: 90%+ user satisfaction
- Form state preservation: All edit operations
