# Error Message Migration Checklist

Track your progress as you migrate files to use centralized error messages.

## Quick Start

1. Open `MIGRATION_EXAMPLES.md` for complete before/after examples
2. Look at placeholder classes at bottom of `app/utils/error_messages.py`
3. Migrate files one at a time
4. Check off as you complete each file

---

## Files by Priority

### 🟢 EASY (Start Here - ~30 mins total)

- [ ] **Timers** - `app/blueprints/timers/routes.py` (3 violations)
  - Lines: 106, 140, 154
  - See Example 1 in MIGRATION_EXAMPLES.md
  - Messages already exist in error_messages.py!

- [ ] **Bulk Stock** - `app/routes/bulk_stock_routes.py` (9 violations)
  - Lines: 23, 29, 32, 79, 83, 92, 97, 111, 114
  - See Example 2 in MIGRATION_EXAMPLES.md
  - Placeholder: `_BulkStockMessages`

- [ ] **App Routes** - `app/routes/app_routes.py` (4 violations)
  - Lines: 25, 37, 44, 123
  - Placeholder: `_AppRoutesMessages`

- [ ] **Tools Routes** - `app/routes/tools_routes.py` (5 violations)
  - All same pattern (unavailable messages)
  - Placeholder: `_ToolsRoutesMessages`

### 🟡 MEDIUM (Next - ~1-2 hours total)

- [ ] **Inventory** - `app/blueprints/inventory/routes.py` (~12 violations)
  - Lines: 236, 371, 376, 386, 392, 395, 409, 415, 465, 512
  - See Example 3 in MIGRATION_EXAMPLES.md
  - **Most messages already exist!** Only 2 new ones needed
  - Placeholder: `_InventoryMessages`

- [ ] **Recipes** - `app/blueprints/recipes/routes.py` (8 violations)
  - Lines: 117, 176, 201, 259, 263, 359, 429, 455
  - Most messages already exist
  - Placeholder: `_RecipesMessages`

- [ ] **Product Inventory** - `app/blueprints/products/product_inventory_routes.py` (12 violations)
  - Mostly uses existing messages
  - Check for generic "Failed to..." errors

- [ ] **Batches Start** - `app/blueprints/batches/start_batch.py` (5 violations)
  - Already has error details in service layer
  - Just need to pass them through

- [ ] **Reservations API** - `app/blueprints/api/reservation_routes.py` (4 violations)
  - Simple API errors
  - Messages mostly exist

### 🔴 LARGE (Last - ~2-3 hours total)

- [ ] **Developer Routes** - `app/blueprints/developer/routes.py` (22 violations)
  - Lines: 216, 220, 224, 228, 234, 380, 403, 537, 727, etc.
  - Lots of validation messages
  - Placeholder: `_DeveloperRoutesMessages`

- [ ] **Billing Routes** - `app/blueprints/billing/routes.py` (42 violations)
  - Lines: 29, 38, 80, 91, 98, 111, 115, 128, 135, etc.
  - Mix of errors, warnings, success messages
  - Placeholder: `_BillingRoutesMessages`

### 📦 Remaining Files (Variable)

- [ ] **Settings** - `app/blueprints/settings/routes.py` (~14 violations)
- [ ] **Organization** - `app/blueprints/organization/routes.py` (~11 violations)
- [ ] **Products** - `app/blueprints/products/products.py` (~17 violations)
- [ ] **Product Variants** - `app/blueprints/products/product_variants.py` (~14 violations)
- [ ] **Product SKU** - `app/blueprints/products/sku.py` (~9 violations)
- [ ] **Batches** - `app/blueprints/batches/routes.py` (~12 violations)
- [ ] **Finish Batch** - `app/blueprints/batches/finish_batch.py` (~6 violations)
- [ ] **Cancel Batch** - `app/blueprints/batches/cancel_batch.py` (~4 violations)
- [ ] **Conversion** - `app/blueprints/conversion/routes.py` (~18 violations)
- [ ] **Developer Addons** - `app/blueprints/developer/addons.py` (~8 violations)
- [ ] **Developer System Roles** - `app/blueprints/developer/system_roles.py` (~1 violation)
- [ ] **Developer Subscription Tiers** - `app/blueprints/developer/subscription_tiers.py` (~16 violations)
- [ ] **Auth Routes** - `app/blueprints/auth/routes.py` (~29 violations)
- [ ] **Whop Auth** - `app/blueprints/auth/whop_auth.py` (~2 violations)
- [ ] **Production Planning** - `app/blueprints/production_planning/routes.py` (~1 violation)
- [ ] **Signup Service** - `app/services/signup_service.py` (~5 violations)
- [ ] **Middleware** - `app/middleware.py` (~4 violations)
- [ ] **Permissions** - `app/utils/permissions.py` (~2 violations)

---

## Progress Tracker

### Overall Stats
- **Total files to migrate**: ~35 files
- **Total violations**: ~255
- **Files completed**: 0
- **Violations remaining**: 255

### Quick Commands

```bash
# Check your progress
python3 tests/test_error_message_compliance.py 2>&1 | grep "Total violations"

# Test a specific file after migration
pytest tests/test_error_message_compliance.py -v -k "test_no_hardcoded"

# See which files still have violations
python3 tests/test_error_message_compliance.py 2>&1 | grep "File:" | sort | uniq -c
```

---

## Migration Steps (Copy-Paste)

For each file:

### Step 1: Check placeholder class
```bash
# Look at bottom of error_messages.py
grep -A 20 "class _YourFileMessages" app/utils/error_messages.py
```

### Step 2: Copy messages to main classes
Copy constants from `_YourFileMessages` to:
- `ErrorMessages` for errors
- `SuccessMessages` for success messages
- `WarningMessages` for warnings

### Step 3: Add imports to route file
```python
from app.utils.error_messages import ErrorMessages as EM
from app.utils.error_messages import SuccessMessages as SM
from app.utils.api_responses import APIResponse
```

### Step 4: Replace violations
See MIGRATION_EXAMPLES.md for patterns

### Step 5: Re-test
```bash
python3 tests/test_error_message_compliance.py
```

### Step 6: Check off this file above! ✅

---

## Time Estimates

- **Easy files (🟢)**: 5-10 min each → ~30 min total
- **Medium files (🟡)**: 10-20 min each → 1-2 hours total  
- **Large files (🔴)**: 30-60 min each → 2-3 hours total
- **Remaining files**: 5-15 min each → 2-3 hours total

**Total estimated time**: 5-8 hours (or 1-2 weeks doing 5-10 files per day)

---

## Celebration Milestones 🎉

- [ ] **First file complete!** (Timers - easiest)
- [ ] **10 files done** (~40% complete)
- [ ] **All easy files done** (Good momentum!)
- [ ] **All medium files done** (You're crushing it!)
- [ ] **100 violations fixed** (More than halfway!)
- [ ] **All large files done** (Home stretch!)
- [ ] **< 50 violations remaining** (Almost there!)
- [ ] **< 10 violations remaining** (So close!)
- [ ] **ALL VIOLATIONS FIXED!** 🎊🎉🚀

---

## Tips

### Go Fastest By:
1. Start with EASY files (quick wins, build momentum)
2. Do similar files together (batch context)
3. Use find & replace for repetitive patterns
4. Take breaks between large files

### Avoid Burnout:
- Don't try to do it all in one sitting
- Celebrate small wins
- 5-10 files per day is plenty
- The system prevents new violations, so no rush!

### Get Help:
- See MIGRATION_EXAMPLES.md for complete examples
- Check error_messages.py for existing messages
- Run tests frequently to see progress

---

## Notes

Add your own notes here as you go:

- 
- 
- 

