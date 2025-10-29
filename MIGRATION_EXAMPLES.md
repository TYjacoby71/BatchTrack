# Error Message Migration Examples

This file shows complete before/after examples for migrating each file type.
Follow these patterns when migrating your code.

---

## Example 1: Timers (SIMPLE - 3 violations)

### File: `app/blueprints/timers/routes.py`

### BEFORE (Lines 106, 140, 154):
```python
@timers_bp.route('/api/stop-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_stop_timer(timer_id):
    """Stop/complete an active timer"""
    try:
        success = TimerService.stop_timer(timer_id)
        if success:
            timer_status = TimerService.get_timer_status(timer_id)
            return jsonify({
                'success': True, 
                'message': 'Timer completed',
                'end_time': timer_status.get('end_time')
            })
        else:
            return jsonify({'error': 'Failed to stop timer'}), 400  # ❌ HARDCODED
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/pause-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_pause_timer(timer_id):
    """Pause an active timer"""
    try:
        success = TimerService.pause_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer paused'})
        else:
            return jsonify({'error': 'Failed to pause timer'}), 400  # ❌ HARDCODED
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timers_bp.route('/api/resume-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_resume_timer(timer_id):
    """Resume a paused timer"""
    try:
        success = TimerService.resume_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer resumed'})
        else:
            return jsonify({'error': 'Failed to resume timer'}), 400  # ❌ HARDCODED
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### AFTER (Fixed):
```python
# ADD AT TOP OF FILE:
from app.utils.error_messages import ErrorMessages as EM
from app.utils.api_responses import APIResponse

@timers_bp.route('/api/stop-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_stop_timer(timer_id):
    """Stop/complete an active timer"""
    try:
        success = TimerService.stop_timer(timer_id)
        if success:
            timer_status = TimerService.get_timer_status(timer_id)
            return jsonify({
                'success': True, 
                'message': 'Timer completed',
                'end_time': timer_status.get('end_time')
            })
        else:
            # ✅ FIXED - Use centralized message and APIResponse
            return APIResponse.error(
                message=EM.TIMER_STOP_FAILED,
                errors={'timer_id': timer_id},
                status_code=400
            )
    except Exception as e:
        return APIResponse.error(
            message=str(e),
            errors={'timer_id': timer_id},
            status_code=500
        )

@timers_bp.route('/api/pause-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_pause_timer(timer_id):
    """Pause an active timer"""
    try:
        success = TimerService.pause_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer paused'})
        else:
            # ✅ FIXED
            return APIResponse.error(
                message=EM.TIMER_PAUSE_FAILED,
                errors={'timer_id': timer_id},
                status_code=400
            )
    except Exception as e:
        return APIResponse.error(
            message=str(e),
            errors={'timer_id': timer_id},
            status_code=500
        )

@timers_bp.route('/api/resume-timer/<int:timer_id>', methods=['POST'])
@login_required
def api_resume_timer(timer_id):
    """Resume a paused timer"""
    try:
        success = TimerService.resume_timer(timer_id)
        if success:
            return jsonify({'success': True, 'message': 'Timer resumed'})
        else:
            # ✅ FIXED
            return APIResponse.error(
                message=EM.TIMER_RESUME_FAILED,
                errors={'timer_id': timer_id},
                status_code=400
            )
    except Exception as e:
        return APIResponse.error(
            message=str(e),
            errors={'timer_id': timer_id},
            status_code=500
        )
```

### Messages Already in error_messages.py:
These are already defined in `ErrorMessages` class - nothing to add!
- `TIMER_STOP_FAILED`
- `TIMER_PAUSE_FAILED`
- `TIMER_RESUME_FAILED`

---

## Example 2: Bulk Stock (SIMPLE - 9 violations)

### File: `app/routes/bulk_stock_routes.py`

### STEP 1: Add messages to error_messages.py
```python
# Add to ErrorMessages class in app/utils/error_messages.py

class ErrorMessages:
    # ... existing messages ...
    
    # ==================== BULK STOCK CHECK ====================
    BULK_STOCK_SELECT_RECIPE = "Please select at least one recipe"
    BULK_STOCK_SCALE_POSITIVE = "Scale must be greater than 0"
    BULK_STOCK_SCALE_INVALID = "Invalid scale value"
    BULK_STOCK_CHECK_FAILED = "Bulk stock check failed"
    BULK_STOCK_ERROR = "Error checking stock: {reason}"
    BULK_STOCK_NO_RESULTS = "No stock check results available"
    BULK_STOCK_NO_RESTOCK_NEEDED = "No items need restocking"
    BULK_STOCK_PROCESSING_FAILED = "Bulk stock processing failed: {reason}"
    BULK_STOCK_CSV_ERROR = "Database error exporting CSV."
```

### STEP 2: Update bulk_stock_routes.py

### BEFORE (Lines 23, 29, 32, 79, 83, 92, 97, 111, 114):
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    try:
        recipes = Recipe.scoped().all()
        summary = {}

        if request.method == 'POST':
            selected_ids = request.form.getlist('recipe_ids')
            if not selected_ids:
                flash('Please select at least one recipe')  # ❌ Line 23
                return redirect(url_for('bulk_stock.bulk_stock_check'))

            try:
                scale = float(request.form.get('scale', 1.0))
                if scale <= 0:
                    flash('Scale must be greater than 0')  # ❌ Line 29
                    return redirect(url_for('bulk_stock.bulk_stock_check'))
            except ValueError:
                flash('Invalid scale value')  # ❌ Line 32
                return redirect(url_for('bulk_stock.bulk_stock_check'))
            
            # ... stock check logic ...
            
            if bulk_results['success']:
                # ... process results ...
                session['bulk_summary'] = summary
            else:
                flash('Bulk stock check failed', 'error')  # ❌ Line 79

        return render_template('bulk_stock_check.html', recipes=recipes, summary=summary)
    except Exception as e:
        flash(f'Error checking stock: {str(e)}')  # ❌ Line 83
        return redirect(url_for('bulk_stock.bulk_stock_check'))

@bulk_stock_bp.route('/bulk-check/csv')
@login_required
def export_shopping_list_csv():
    try:
        summary = session.get('bulk_summary', [])
        if not summary:
            flash('No stock check results available')  # ❌ Line 92
            return redirect(url_for('bulk_stock.bulk_stock_check'))

        missing = [item for item in summary if item['status'] in ['LOW', 'NEEDED']]
        if not missing:
            flash('No items need restocking')  # ❌ Line 97
            return redirect(url_for('bulk_stock.bulk_stock_check'))
        
        # ... CSV generation ...
        
    except ValueError as e:
        flash(f"Bulk stock processing failed: {e}", "warning")  # ❌ Line 111
        return redirect(request.referrer or url_for('stock.bulk_check'))
    except SQLAlchemyError as e:
        flash("Database error exporting CSV.", "danger")  # ❌ Line 114
        return redirect(url_for('bulk_stock.bulk_stock_check'))
```

### AFTER (Fixed):
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
# ✅ ADD THESE IMPORTS
from app.utils.error_messages import ErrorMessages as EM

bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    try:
        recipes = Recipe.scoped().all()
        summary = {}

        if request.method == 'POST':
            selected_ids = request.form.getlist('recipe_ids')
            if not selected_ids:
                flash(EM.BULK_STOCK_SELECT_RECIPE, 'error')  # ✅ FIXED Line 23
                return redirect(url_for('bulk_stock.bulk_stock_check'))

            try:
                scale = float(request.form.get('scale', 1.0))
                if scale <= 0:
                    flash(EM.BULK_STOCK_SCALE_POSITIVE, 'error')  # ✅ FIXED Line 29
                    return redirect(url_for('bulk_stock.bulk_stock_check'))
            except ValueError:
                flash(EM.BULK_STOCK_SCALE_INVALID, 'error')  # ✅ FIXED Line 32
                return redirect(url_for('bulk_stock.bulk_stock_check'))
            
            # ... stock check logic ...
            
            if bulk_results['success']:
                # ... process results ...
                session['bulk_summary'] = summary
            else:
                flash(EM.BULK_STOCK_CHECK_FAILED, 'error')  # ✅ FIXED Line 79

        return render_template('bulk_stock_check.html', recipes=recipes, summary=summary)
    except Exception as e:
        flash(EM.BULK_STOCK_ERROR.format(reason=str(e)), 'error')  # ✅ FIXED Line 83
        return redirect(url_for('bulk_stock.bulk_stock_check'))

@bulk_stock_bp.route('/bulk-check/csv')
@login_required
def export_shopping_list_csv():
    try:
        summary = session.get('bulk_summary', [])
        if not summary:
            flash(EM.BULK_STOCK_NO_RESULTS, 'error')  # ✅ FIXED Line 92
            return redirect(url_for('bulk_stock.bulk_stock_check'))

        missing = [item for item in summary if item['status'] in ['LOW', 'NEEDED']]
        if not missing:
            flash(EM.BULK_STOCK_NO_RESTOCK_NEEDED, 'info')  # ✅ FIXED Line 97
            return redirect(url_for('bulk_stock.bulk_stock_check'))
        
        # ... CSV generation ...
        
    except ValueError as e:
        flash(EM.BULK_STOCK_PROCESSING_FAILED.format(reason=str(e)), 'warning')  # ✅ FIXED Line 111
        return redirect(request.referrer or url_for('stock.bulk_check'))
    except SQLAlchemyError as e:
        flash(EM.BULK_STOCK_CSV_ERROR, 'error')  # ✅ FIXED Line 114
        return redirect(url_for('bulk_stock.bulk_stock_check'))
```

---

## Example 3: Inventory (MEDIUM - ~12 violations)

### File: `app/blueprints/inventory/routes.py`

### STEP 1: Add NEW messages to error_messages.py
```python
# Most inventory messages already exist!
# Only need to add these 2:

class ErrorMessages:
    # ... existing messages ...
    
    # ==================== INVENTORY ====================
    # Most already exist, just add:
    INVENTORY_ACCESS_DENIED_ALT = "Inventory item not found or access denied."  # Line 236
    INVENTORY_RECOUNT_QUANTITY_INVALID = "Invalid quantity provided for recount."  # Line 512
```

### STEP 2: Update inventory/routes.py

### BEFORE (Partial - showing key violations):
```python
from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template

@inventory_bp.route('/view/<int:id>')
@login_required
def view_inventory(id):
    # ... code ...
    if not item:
        flash('Inventory item not found or access denied.', 'error')  # ❌ Line 236
        return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:item_id>', methods=['POST'])
@login_required
@permission_required('inventory.adjust')
def adjust_inventory(item_id):
    item = db.session.get(InventoryItem, int(item_id))
    if not item:
        flash("Inventory item not found.", "error")  # ❌ Line 371
        return redirect(url_for('.list_inventory'))

    if not can_edit_inventory_item(item):
        flash('Permission denied.', 'error')  # ❌ Line 376
        return redirect(url_for('.list_inventory'))

    change_type = form_data.get('change_type', '').strip().lower()
    if not change_type:
        flash("Adjustment type is required.", "error")  # ❌ Line 386
        return redirect(url_for('.view_inventory', id=item_id))

    try:
        quantity = float(form_data.get('quantity', 0.0))
        if quantity <= 0:
            flash("Quantity must be greater than 0.", "error")  # ❌ Line 392
            return redirect(url_for('.view_inventory', id=item_id))
    except (ValueError, TypeError):
        flash("Invalid quantity provided.", "error")  # ❌ Line 395
        return redirect(url_for('.view_inventory', id=item_id))
```

### AFTER (Fixed):
```python
from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template
# ✅ ADD THIS IMPORT
from app.utils.error_messages import ErrorMessages as EM

@inventory_bp.route('/view/<int:id>')
@login_required
def view_inventory(id):
    # ... code ...
    if not item:
        flash(EM.INVENTORY_ACCESS_DENIED_ALT, 'error')  # ✅ FIXED Line 236
        return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:item_id>', methods=['POST'])
@login_required
@permission_required('inventory.adjust')
def adjust_inventory(item_id):
    item = db.session.get(InventoryItem, int(item_id))
    if not item:
        flash(EM.INVENTORY_NOT_FOUND, 'error')  # ✅ FIXED Line 371 (message already exists!)
        return redirect(url_for('.list_inventory'))

    if not can_edit_inventory_item(item):
        flash(EM.PERMISSION_DENIED, 'error')  # ✅ FIXED Line 376 (message already exists!)
        return redirect(url_for('.list_inventory'))

    change_type = form_data.get('change_type', '').strip().lower()
    if not change_type:
        flash(EM.INVENTORY_CHANGE_TYPE_REQUIRED, 'error')  # ✅ FIXED Line 386 (already exists!)
        return redirect(url_for('.view_inventory', id=item_id))

    try:
        quantity = float(form_data.get('quantity', 0.0))
        if quantity <= 0:
            flash(EM.INVENTORY_QUANTITY_POSITIVE, 'error')  # ✅ FIXED Line 392 (already exists!)
            return redirect(url_for('.view_inventory', id=item_id))
    except (ValueError, TypeError):
        flash(EM.INVENTORY_QUANTITY_INVALID, 'error')  # ✅ FIXED Line 395 (already exists!)
        return redirect(url_for('.view_inventory', id=item_id))
```

**Note:** Most inventory messages already exist! Only 2 new ones needed.

---

## Quick Reference: Your Workflow

For each file you're migrating:

### 1. Find the placeholder class in error_messages.py
Look for `class _YourFileMessages:` at the bottom of error_messages.py

### 2. Copy messages to the appropriate class
Move the constants from `_YourFileMessages` to `ErrorMessages`, `SuccessMessages`, or `WarningMessages`

### 3. Add imports to your route file
```python
from app.utils.error_messages import ErrorMessages as EM
from app.utils.error_messages import SuccessMessages as SM
from app.utils.api_responses import APIResponse  # For JSON routes
```

### 4. Replace each violation
- `flash('error string', 'error')` → `flash(EM.YOUR_ERROR, 'error')`
- `jsonify({'error': 'string'})` → `APIResponse.error(message=EM.YOUR_ERROR, ...)`

### 5. Test
```bash
# Re-run compliance test to see violations decrease
python3 tests/test_error_message_compliance.py
```

---

## Pattern Summary

### HTML Routes (uses flash):
```python
# BEFORE
flash('Error message here', 'error')

# AFTER
from app.utils.error_messages import ErrorMessages as EM
flash(EM.YOUR_ERROR, 'error')
```

### API Routes (uses jsonify):
```python
# BEFORE
return jsonify({'error': 'Error message'}), 400

# AFTER  
from app.utils.api_responses import APIResponse
from app.utils.error_messages import ErrorMessages as EM
return APIResponse.error(
    message=EM.YOUR_ERROR,
    errors={'field': 'value'},
    status_code=400
)
```

### With Dynamic Values:
```python
# BEFORE
flash(f'Error: {reason}', 'error')

# AFTER
flash(EM.YOUR_ERROR.format(reason=reason), 'error')
```

---

## Next Files to Migrate

Easiest to hardest:
1. ✅ **Timers** - 3 violations, all jsonify (SHOWN ABOVE)
2. ✅ **Bulk Stock** - 9 violations, all flash (SHOWN ABOVE)
3. ✅ **Inventory** - 12 violations, mostly already exist (SHOWN ABOVE)
4. **Recipes** - 8 violations, mix of flash
5. **Developer Routes** - 22 violations, lots of validation
6. **Billing Routes** - 42 violations, mix of everything

Use the placeholder classes in error_messages.py to guide you!
