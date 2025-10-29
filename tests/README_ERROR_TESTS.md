# Error Message Compliance Tests

## Overview

These tests enforce the centralized error message protocol across the codebase.

## Test Files

### 1. `test_error_message_compliance.py` (Comprehensive)
Full compliance checker that scans all route files for:
- ✅ Hardcoded error strings (should use `EM.*` constants)
- ✅ Flash messages without categories
- ✅ Jsonify error dicts (should use `APIResponse`)
- ✅ Missing ErrorMessages imports in route files
- ✅ HTML tags in error messages
- ✅ F-strings in message definitions

**Run with:**
```bash
pytest tests/test_error_message_compliance.py -v
```

**Run specific test:**
```bash
pytest tests/test_error_message_compliance.py::TestErrorMessageCompliance::test_no_hardcoded_error_flash -v
```

### 2. `test_error_compliance_simple.py` (Quick Check)
Lighter weight test that checks:
- ✅ error_messages.py exists and has classes
- ✅ layout.html uses message categories
- ✅ Documentation exists
- ⚠️  Sample scan of route files (warning only)

**Run with:**
```bash
pytest tests/test_error_compliance_simple.py -v
```

---

## Running the Tests

### Run All Compliance Tests
```bash
cd /workspace
pytest tests/test_error_message_compliance.py -v
```

### Run with Detailed Output
```bash
pytest tests/test_error_message_compliance.py -v -s
```

### Run and Continue on Failure (see all violations)
```bash
pytest tests/test_error_message_compliance.py -v --tb=short
```

### Run Just Infrastructure Tests (quick)
```bash
pytest tests/test_error_message_compliance.py::TestErrorMessageCompliance::test_error_messages_file_valid -v
pytest tests/test_error_message_compliance.py::TestErrorMessageCompliance::test_layout_template_uses_categories -v
```

### Standalone Scan (No pytest needed)
```bash
cd /workspace
python3 tests/test_error_message_compliance.py
```

This runs a quick scan and outputs violations directly to console.

---

## What Each Test Checks

### ✅ Infrastructure Tests (Always Run These)

#### `test_error_messages_file_valid`
- Checks `app/utils/error_messages.py` exists
- Validates Python syntax
- Ensures required classes exist (ErrorMessages, SuccessMessages)
- Verifies no f-strings in message definitions

#### `test_error_messages_no_html`
- Ensures no HTML tags in error messages
- Messages should be plain text only

#### `test_layout_template_uses_categories`
- Checks layout.html uses `get_flashed_messages(with_categories=true)`
- Verifies proper category mapping (error→danger, success→success, etc.)

#### `test_error_protocol_documentation_exists`
- Ensures developer documentation exists
- Required: ERROR_MESSAGE_PROTOCOL.md, ROUTE_DEVELOPMENT_GUIDE.md

---

### 🔍 Code Quality Tests (Run During Development)

#### `test_no_hardcoded_error_flash`
Finds flash() calls with hardcoded error strings:

```python
# ❌ BAD (will be caught)
flash('Inventory item not found', 'error')

# ✅ GOOD
from app.utils.error_messages import ErrorMessages as EM
flash(EM.INVENTORY_NOT_FOUND, 'error')
```

#### `test_flash_has_category`
Ensures all flash() calls include a category:

```python
# ❌ BAD (will be caught)
flash('Some message')

# ✅ GOOD
flash(EM.SOME_MESSAGE, 'error')  # or 'success', 'warning', 'info'
```

#### `test_use_api_response_not_jsonify`
Ensures API routes use APIResponse:

```python
# ❌ BAD (will be caught)
return jsonify({'error': 'Not found'}), 404

# ✅ GOOD
return APIResponse.error(
    message=EM.ITEM_NOT_FOUND,
    errors={'item_id': item_id},
    status_code=404
)
```

#### `test_route_files_import_error_messages`
Checks that route files import ErrorMessages (warning only):

```python
# ✅ GOOD - Add to top of route files
from app.utils.error_messages import ErrorMessages as EM
from app.utils.error_messages import SuccessMessages as SM
```

---

## Understanding Test Output

### When Tests Pass ✅
```
test_error_messages_file_valid PASSED
test_no_hardcoded_error_flash PASSED
test_flash_has_category PASSED
```
Great! Your code follows the error message protocol.

### When Tests Fail ❌
The test output shows:
1. **File and line number** where violation occurs
2. **Type of violation** (HARDCODED_ERROR_FLASH, FLASH_NO_CATEGORY, etc.)
3. **The problematic code snippet**
4. **Suggestion for fixing it**

Example output:
```
HARDCODED ERROR MESSAGES FOUND
================================================================================

File: app/blueprints/inventory/routes.py
Line: 45
Issue: Hardcoded error message in flash(): "Inventory item not found"
Fix: Use ErrorMessages constant: flash(EM.INVENTORY_NOT_FOUND, 'error')
--------------------------------------------------------------------------------

Total violations: 1

These should use centralized ErrorMessages:
  from app.utils.error_messages import ErrorMessages as EM
  flash(EM.YOUR_ERROR, 'error')
```

---

## CI/CD Integration

### Add to GitHub Actions / CI Pipeline

```yaml
# .github/workflows/tests.yml
- name: Check Error Message Compliance
  run: |
    pytest tests/test_error_message_compliance.py -v
```

### Pre-commit Hook (Optional)

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/test_error_compliance_simple.py -q
if [ $? -ne 0 ]; then
    echo "Error message compliance check failed. Please fix violations."
    exit 1
fi
```

---

## Fixing Violations

### Step 1: Add Message to error_messages.py
```python
# app/utils/error_messages.py

class ErrorMessages:
    # Find the appropriate section
    # ==================== YOUR FEATURE ====================
    FEATURE_NOT_FOUND = "Feature not found."
    FEATURE_CREATE_FAILED = "Failed to create feature: {reason}"
```

### Step 2: Update Your Route
```python
# Before
flash('Feature not found', 'error')

# After
from app.utils.error_messages import ErrorMessages as EM
flash(EM.FEATURE_NOT_FOUND, 'error')
```

### Step 3: Re-run Tests
```bash
pytest tests/test_error_message_compliance.py -v
```

---

## Gradual Migration Strategy

You don't need to fix everything at once:

### Phase 1: Foundation (Done ✅)
- [x] error_messages.py created
- [x] layout.html updated
- [x] Documentation written
- [x] Tests created

### Phase 2: New Code (Enforce Now)
- All NEW routes must use centralized messages
- All NEW features must follow the protocol
- Tests will catch violations in new code

### Phase 3: Legacy Code (Migrate Gradually)
- Fix violations when you touch old code
- No rush - happens organically
- Tests track progress

---

## Test Configuration

### Pytest Configuration (pytest.ini or pyproject.toml)

```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

# Show warnings for error message compliance
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
]

markers = [
    "compliance: Error message compliance tests",
]
```

### Mark Compliance Tests

```python
# Add to test classes
@pytest.mark.compliance
class TestErrorMessageCompliance:
    ...
```

Then run only compliance tests:
```bash
pytest -m compliance
```

---

## Troubleshooting

### "No module named 'pytest'"
```bash
pip install pytest
```

### "Too many violations to fix"
Start with infrastructure tests:
```bash
pytest tests/test_error_message_compliance.py::TestErrorMessageCompliance::test_error_messages_file_valid -v
```

Then tackle violations file by file:
1. Pick one route file
2. Add messages to error_messages.py
3. Update the route file
4. Re-run tests
5. Repeat

### "False positives in tests"
Some patterns might trigger false positives. Update the regex patterns in the test file if needed, or add exceptions for legitimate use cases.

---

## Metrics & Reporting

### Generate Compliance Report
```bash
pytest tests/test_error_message_compliance.py --tb=no -v > compliance_report.txt
```

### Count Violations
```bash
python3 tests/test_error_message_compliance.py 2>&1 | grep "Total violations"
```

### Track Progress Over Time
Run tests regularly and track:
- Number of files compliant
- Number of violations remaining
- Compliance percentage

---

## Questions?

- See: `/docs/ERROR_MESSAGE_PROTOCOL.md` for the full protocol
- See: `/docs/ROUTE_DEVELOPMENT_GUIDE.md` for examples
- See: `/docs/QUICK_REFERENCE_ERRORS.md` for quick reference

---

## Quick Commands Reference

```bash
# Run all compliance tests
pytest tests/test_error_message_compliance.py -v

# Run simple/fast tests only
pytest tests/test_error_compliance_simple.py -v

# Run standalone scan (no pytest)
python3 tests/test_error_message_compliance.py

# Run and show all violations
pytest tests/test_error_message_compliance.py --tb=short

# Run specific test
pytest tests/test_error_message_compliance.py::TestErrorMessageCompliance::test_no_hardcoded_error_flash

# Run with coverage
pytest tests/test_error_message_compliance.py --cov=app/utils/error_messages

# Generate HTML report
pytest tests/test_error_message_compliance.py --html=report.html
```
