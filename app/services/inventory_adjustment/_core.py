
import logging
from datetime import datetime
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.services.unit_conversion import ConversionEngine
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import (
    _calculate_deduction_plan_internal, _execute_deduction_plan_internal, 
    _record_deduction_plan_internal, _internal_add_fifo_entry_enhanced,
    _calculate_addition_plan_internal, _execute_addition_plan_internal,
    _record_addition_plan_internal
)
from ._recount_logic import handle_recount_adjustment
from ._audit import log_inventory_adjustment

logger = logging.getLogger(__name__)

def process_inventory_adjustment(item_id, adjustment_type, quantity=None, 
                               target_quantity=None, notes=None, created_by=None,
                               cost_per_unit=None, lot_number=None, expiration_date=None):
    """
    Main entry point for all inventory adjustments.
    
    Args:
        item_id: ID of inventory item to adjust
        adjustment_type: Type of adjustment ('add', 'use', 'waste', 'recount', 'correction')
        quantity: Quantity to add/deduct (for add/use/waste/correction)
        target_quantity: Target quantity (for recount)
        notes: Optional notes for the adjustment
        created_by: User ID making the adjustment
        cost_per_unit: Cost per unit for new inventory (optional)
        lot_number: Lot number for new inventory (optional)
        expiration_date: Expiration date for new inventory (optional)
        
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        # Validate inputs
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, f"Item {item_id} not found"
            
        if adjustment_type not in ['add', 'use', 'waste', 'recount', 'correction']:
            return False, f"Invalid adjustment type: {adjustment_type}"
            
        # Validate quantity inputs based on adjustment type
        if adjustment_type == 'recount':
            if target_quantity is None:
                return False, "Target quantity required for recount adjustment"
            try:
                target_quantity = float(target_quantity)
                if target_quantity < 0:
                    return False, "Target quantity cannot be negative"
            except (ValueError, TypeError):
                return False, "Invalid target quantity"
        else:
            if quantity is None:
                return False, f"Quantity required for {adjustment_type} adjustment"
            try:
                quantity = float(quantity)
                if quantity <= 0:
                    return False, "Quantity must be positive"
            except (ValueError, TypeError):
                return False, "Invalid quantity"
                
        # Round values for consistent handling
        if quantity is not None:
            quantity = ConversionEngine.round_value(quantity, 3)
        if target_quantity is not None:
            target_quantity = ConversionEngine.round_value(target_quantity, 3)
            
        # Route to appropriate handler
        if adjustment_type == 'recount':
            success = handle_recount_adjustment(
                item_id, target_quantity, notes, created_by, item.type
            )
            if success:
                log_inventory_adjustment(
                    item_id, adjustment_type, target_quantity, notes, created_by
                )
            return success, None if success else "Recount adjustment failed"
            
        elif adjustment_type == 'add':
            return _handle_addition(
                item_id, quantity, notes, created_by, cost_per_unit, 
                lot_number, expiration_date, item
            )
            
        elif adjustment_type in ['use', 'waste', 'correction']:
            return _handle_deduction(
                item_id, quantity, adjustment_type, notes, created_by, item
            )
            
        else:
            return False, f"Unhandled adjustment type: {adjustment_type}"
            
    except Exception as e:
        logger.error(f"Error processing inventory adjustment: {e}")
        db.session.rollback()
        return False, f"Adjustment failed: {str(e)}"


def _handle_addition(item_id, quantity, notes, created_by, cost_per_unit, 
                    lot_number, expiration_date, item):
    """Handle inventory additions (add stock)"""
    try:
        # Use item's cost if not provided
        if cost_per_unit is None:
            cost_per_unit = item.cost_per_unit or 0.0
        else:
            cost_per_unit = float(cost_per_unit)
            
        # Create new FIFO entry
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item_id,
            quantity=quantity,
            change_type='add',
            unit=item.unit,
            notes=notes or "Stock addition",
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            lot_number=lot_number,
            expiration_date=expiration_date
        )
        
        if not success:
            return False, f"Failed to add stock: {error}"
            
        # Update parent item quantity
        item.quantity = ConversionEngine.round_value(
            (item.quantity or 0) + quantity, 3
        )
        
        # Update cost if this is the first stock
        if item.cost_per_unit is None or item.cost_per_unit == 0:
            item.cost_per_unit = cost_per_unit
            
        db.session.commit()
        
        # Log the adjustment
        log_inventory_adjustment(item_id, 'add', quantity, notes, created_by)
        
        return True, None
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in addition handling: {e}")
        return False, f"Addition failed: {str(e)}"


def _handle_deduction(item_id, quantity, change_type, notes, created_by, item):
    """Handle inventory deductions (use, waste, correction)"""
    try:
        # Calculate deduction plan
        deduction_plan, error = _calculate_deduction_plan_internal(
            item_id, quantity, change_type
        )
        
        if error:
            return False, error
            
        # Execute the deduction
        _execute_deduction_plan_internal(deduction_plan, item_id)
        
        # Record the deduction
        _record_deduction_plan_internal(
            item_id, deduction_plan, change_type, 
            notes or f"Stock {change_type}", created_by=created_by
        )
        
        # Update parent item quantity
        item.quantity = ConversionEngine.round_value(
            (item.quantity or 0) - quantity, 3
        )
        
        db.session.commit()
        
        # Log the adjustment
        log_inventory_adjustment(item_id, change_type, -quantity, notes, created_by)
        
        return True, None
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in deduction handling: {e}")
        return False, f"Deduction failed: {str(e)}"
