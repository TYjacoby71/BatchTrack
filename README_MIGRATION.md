# Error Message Migration Guide

## What's Been Set Up For You

✅ **Centralized Messages** - `app/utils/error_messages.py` with 90+ base messages  
✅ **Pre-created Placeholders** - All ~255 violations mapped out for you  
✅ **Complete Examples** - 3 full before/after examples  
✅ **Testing** - Automated tests to check progress  
✅ **Documentation** - Full protocol and guides  

## Quick Start - Migrate Your First File (5 minutes)

### 1. Look at the example
```bash
cat MIGRATION_EXAMPLES.md
# See "Example 1: Timers" - complete before/after
```

### 2. Open error_messages.py
All your messages are pre-created in placeholder classes at the bottom:
```bash
tail -200 app/utils/error_messages.py
# See _TimersMessages, _BulkStockMessages, etc.
```

### 3. Migrate timers/routes.py (easiest file)
```bash
# Edit the file
vim app/blueprints/timers/routes.py

# Add at top:
from app.utils.error_messages import ErrorMessages as EM
from app.utils.api_responses import APIResponse

# Replace line 106:
# OLD: return jsonify({'error': 'Failed to stop timer'}), 400
# NEW: return APIResponse.error(message=EM.TIMER_STOP_FAILED, errors={'timer_id': timer_id}, status_code=400)

# Repeat for lines 140 and 154
```

### 4. Test it
```bash
python3 tests/test_error_message_compliance.py
# Should show 3 fewer violations!
```

### 5. Repeat for next file
Use MIGRATION_CHECKLIST.md to track progress.

---

## Files to Read

1. **MIGRATION_EXAMPLES.md** - Complete before/after examples for 3 files
2. **MIGRATION_CHECKLIST.md** - Track progress through all 35 files
3. **app/utils/error_messages.py** - All messages (scroll to bottom for placeholders)
4. **docs/ERROR_MESSAGE_PROTOCOL.md** - Complete protocol guide
5. **docs/QUICK_REFERENCE_ERRORS.md** - Copy-paste examples

---

## The Workflow

```
1. Pick a file from MIGRATION_CHECKLIST.md
   ↓
2. Look at placeholder class in error_messages.py
   ↓
3. Copy messages to main ErrorMessages/SuccessMessages class
   ↓
4. Add imports to route file
   ↓
5. Replace each violation (see MIGRATION_EXAMPLES.md)
   ↓
6. Test: python3 tests/test_error_message_compliance.py
   ↓
7. Check off file in MIGRATION_CHECKLIST.md
   ↓
8. Repeat!
```

---

## What's Already Done For You

### In error_messages.py:
- ✅ 90+ base messages already defined
- ✅ All ~255 violations pre-mapped in placeholder classes
- ✅ Line numbers noted for each violation
- ✅ Organized by file for easy reference

### In MIGRATION_EXAMPLES.md:
- ✅ Complete example for Timers (3 violations)
- ✅ Complete example for Bulk Stock (9 violations)
- ✅ Complete example for Inventory (12 violations)

### In MIGRATION_CHECKLIST.md:
- ✅ All 35 files listed
- ✅ Prioritized (easy → hard)
- ✅ Time estimates
- ✅ Progress tracking

---

## Time Investment

- **Per file**: 5-20 minutes
- **Easy files (12)**: ~30 min total
- **Medium files (8)**: 1-2 hours total
- **Large files (2)**: 2-3 hours total
- **Remaining (13)**: 2-3 hours total

**Total**: 5-8 hours (or do 5-10 files per day over 1-2 weeks)

---

## Quick Commands

```bash
# See all placeholder messages
tail -200 app/utils/error_messages.py

# Check progress
python3 tests/test_error_message_compliance.py 2>&1 | grep "Total violations"

# Migrate timers (easiest example)
# See MIGRATION_EXAMPLES.md "Example 1: Timers"

# Track what's done
cat MIGRATION_CHECKLIST.md
```

---

## Questions?

- **Examples?** → MIGRATION_EXAMPLES.md
- **Which file next?** → MIGRATION_CHECKLIST.md
- **How to format?** → docs/QUICK_REFERENCE_ERRORS.md
- **Full protocol?** → docs/ERROR_MESSAGE_PROTOCOL.md

---

## You're Ready!

Everything is set up. Just start with the timers file (5 min) and work through the checklist at your own pace. The tests will track your progress automatically!
