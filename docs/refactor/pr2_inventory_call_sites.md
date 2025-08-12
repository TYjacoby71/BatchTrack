
# PR2 Inventory Call Sites Analysis

## Goal
Map every place inventory is adjusted or FIFO math is called to ensure canonicalization through `app/services/inventory_adjustment.py`.

## Current Canonical Service
✅ **Primary Entry Point**: `app/services/inventory_adjustment.py::process_inventory_adjustment()`
- This function is already positioned as the canonical entry point
- Contains comprehensive FIFO logic, validation, and audit trails
- Has backwards compatibility shims

## Call Site Analysis

### 1. Direct Canonical Service Usage (✅ GOOD)

**Batch Operations:**
- `app/blueprints/batches/finish_batch.py` - Uses `process_inventory_adjustment()` for intermediate ingredients and product creation
- `app/blueprints/batches/add_extra.py` - Uses `process_inventory_adjustment()` for extra ingredients and containers
- `app/blueprints/batches/start_batch.py` - Uses `process_inventory_adjustment()` for ingredient/container deductions
- `app/blueprints/batches/cancel_batch.py` - Uses centralized restoration (references canonical service)

**Service Layer:**
- `app/services/inventory_adjustment.py` - Contains the canonical implementation

### 2. Legacy Compatibility Shims (🟡 NEEDS CLEANUP)

**FIFO Service Backwards Compatibility:**
- `app/blueprints/fifo/services.py::FIFOService.deduct_fifo()` - Shim that delegates to `process_inventory_adjustment()`
- `app/services/inventory_adjustment.py::InventoryAdjustmentService` - Backwards compatibility class

### 3. Internal FIFO Operations (✅ ACCEPTABLE - INTERNAL ONLY)

**Within Canonical Service:**
- `app/blueprints/fifo/services.py::_FIFOService` - Internal implementation used BY the canonical service
- These are properly encapsulated and not called directly from routes

### 4. Potential Direct Calls (🔴 NEEDS INVESTIGATION)

**Routes/Templates:**
- Need to grep for any remaining direct FIFO calls from route handlers
- Need to check if any templates or JavaScript makes direct API calls that bypass canonical service

## Raw Grep Analysis

### Inventory Adjustment Calls
```bash
rg -n "adjust|inventory_adjust|fifo|deduct|consume" app | sort
```

### FIFO Imports
```bash
rg -n "from .*fifo" app | sort  
```

### Canonical Service Usage
```bash
rg -n "inventory_adjustment" app | sort
```

## Pre-Change Grep Results

### All adjustment/FIFO references:
```
app/__init__.py:171:    from app.blueprints.fifo import fifo_bp
app/blueprints/batches/add_extra.py:7:from ...services.inventory_adjustment import process_inventory_adjustment
app/blueprints/batches/add_extra.py:50:            result = process_inventory_adjustment(
app/blueprints/batches/add_extra.py:73:        result = process_inventory_adjustment(
app/blueprints/batches/cancel_batch.py:56:        # Inventory restoration is handled by centralized service
app/blueprints/batches/finish_batch.py:8:from ...services.inventory_adjustment import process_inventory_adjustment
app/blueprints/batches/finish_batch.py:35:                is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(sku.inventory_item_id, 'product')
app/blueprints/batches/finish_batch.py:124:        success = process_inventory_adjustment(
app/blueprints/batches/finish_batch.py:238:        success = process_inventory_adjustment(
app/blueprints/batches/finish_batch.py:274:        success = process_inventory_adjustment(
app/blueprints/batches/start_batch.py:147:                        result = process_inventory_adjustment(
app/blueprints/fifo/__init__.py:27:sys.modules[__name__] = DeprecatedFIFOModule(__name__)
app/blueprints/fifo/services.py:13:⚠️  DEPRECATED FOR EXTERNAL USE ⚠️
app/blueprints/fifo/services.py:15:This module is INTERNAL to app.services.inventory_adjustment only.
app/blueprints/fifo/services.py:18:Use app.services.inventory_adjustment.process_inventory_adjustment() instead.
app/blueprints/fifo/services.py:27:class FIFOService:
app/blueprints/fifo/services.py:28:    """TEMP compatibility shim - use process_inventory_adjustment instead"""
app/blueprints/fifo/services.py:31:    def deduct_fifo(*args, **kwargs):
app/blueprints/fifo/services.py:32:        from app.services.inventory_adjustment import process_inventory_adjustment
app/blueprints/fifo/services.py:33:        return process_inventory_adjustment(*args, **kwargs)
app/services/inventory_adjustment.py:23:def validate_inventory_fifo_sync(inventory_item_id, expected_total=None):
app/services/inventory_adjustment.py:24:    """
app/services/inventory_adjustment.py:25:    Validate that FIFO entries sum to inventory total
app/services/inventory_adjustment.py:47:def validate_inventory_fifo_sync(item_id, item_type=None):
app/services/inventory_adjustment.py:49:    Validates that inventory quantity matches sum of ALL FIFO remaining quantities (including frozen expired)
app/services/inventory_adjustment.py:110:def process_inventory_adjustment(item_id, quantity, change_type, unit=None, notes=None, 
app/services/inventory_adjustment.py:578:class InventoryAdjustmentService:
app/services/inventory_adjustment.py:582:    def adjust_inventory(*args, **kwargs):
app/services/inventory_adjustment.py:583:        """Legacy method - use process_inventory_adjustment instead"""
app/services/inventory_adjustment.py:584:        return process_inventory_adjustment(*args, **kwargs)
app/services/inventory_adjustment.py:587:    def process_inventory_adjustment(*args, **kwargs):
app/services/inventory_adjustment.py:588:        return process_inventory_adjustment(*args, **kwargs)
app/services/inventory_adjustment.py:591:    def validate_inventory_fifo_sync(*args, **kwargs):
app/services/inventory_adjustment.py:592:        return validate_inventory_fifo_sync(*args, **kwargs)
app/static/js/inventory/inventory_adjust.js:1:// Inventory adjustment functionality
app/static/js/inventory/inventory_adjust.js:6:    window.inventoryAdjustmentLoaded = true;
app/static/js/inventory/inventory_adjust.js:8:    // Initialize any inventory adjustment specific functionality here
app/static/js/inventory/inventory_adjust.js:9:    const adjustmentForms = document.querySelectorAll('.adjustment-form');
app/templates/inventory_list.html:12:        <button type="button" class="btn btn-secondary" onclick="toggleUpdateForm()">Update Inventory</button>
```

### FIFO imports:
```
app/blueprints/batches/finish_batch.py:9:from ..fifo.services import FIFOService
app/blueprints/fifo/__init__.py:1:from flask import Blueprint
app/blueprints/fifo/__init__.py:3:fifo_bp = Blueprint('fifo', __name__, template_folder='templates')
app/blueprints/fifo/__init__.py:5:from . import services
app/services/inventory_adjustment.py:316:            FIFOService.calculate_deduction_plan(
app/services/inventory_adjustment.py:329:            FIFOService.execute_deduction_plan(deduction_plan, item_id)
app/services/inventory_adjustment.py:332:            FIFOService.create_deduction_history(
```

### Canonical service usage:
```
app/blueprints/batches/add_extra.py:7:from ...services.inventory_adjustment import process_inventory_adjustment
app/blueprints/batches/finish_batch.py:8:from ...services.inventory_adjustment import process_inventory_adjustment
app/blueprints/batches/start_batch.py:6:from ...services.inventory_adjustment import process_inventory_adjustment
app/services/inventory_adjustment.py:110:def process_inventory_adjustment(item_id, quantity, change_type, unit=None, notes=None,
app/services/inventory_adjustment.py:584:        return process_inventory_adjustment(*args, **kwargs)
app/services/inventory_adjustment.py:587:    def process_inventory_adjustment(*args, **kwargs):
app/services/inventory_adjustment.py:588:        return process_inventory_adjustment(*args, **kwargs)
```

## Analysis Summary

### ✅ ALREADY GOOD
- Batch operations properly use `process_inventory_adjustment()`
- Clear canonical entry point exists
- Backwards compatibility shims in place

### 🟡 CLEANUP NEEDED
- `app/blueprints/batches/finish_batch.py` imports `FIFOService` but should only use canonical service
- Legacy shims can be removed after ensuring no external dependencies

### 🔴 INVESTIGATION NEEDED
- Check if any route handlers directly manipulate inventory without going through canonical service
- Verify JavaScript/AJAX calls use proper endpoints that delegate to canonical service
- Ensure no templates bypass the service layer

## Next Steps for PR2
1. Remove direct `FIFOService` import from `finish_batch.py` 
2. Remove legacy compatibility shims after confirming no external usage
3. Add route → service wiring tests
4. Update greps to confirm canonicalization complete
