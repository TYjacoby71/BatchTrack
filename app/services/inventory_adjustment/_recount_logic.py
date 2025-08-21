
"""
Recount Logic Handler

Handles inventory recounts by comparing current FIFO totals with target quantities
and making appropriate adjustments.
"""

import logging
from app.models import db, InventoryLot
from ._fifo_ops import _handle_deductive_operation_internal, _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

def handle_recount(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None):
    """
    Handle inventory recount operations.
    
    Args:
        item: InventoryItem instance
        quantity: Target quantity for recount (this is the target_quantity)
        change_type: Should be 'recount'
        target_quantity: Alternative way to pass target quantity (for compatibility)
        
    The function compares the current FIFO total with the target and adjusts accordingly.
    """
    try:
        # Use quantity as target, but allow target_quantity override for compatibility
        target_qty = target_quantity if target_quantity is not None else quantity
        
        logger.info(f"RECOUNT: Starting recount for item {item.id} to target {target_qty}")
        
        # Calculate current FIFO total
        current_fifo_total = db.session.query(
            db.func.coalesce(db.func.sum(InventoryLot.remaining_quantity), 0)
        ).filter_by(inventory_item_id=item.id).scalar() or 0.0
        
        delta = float(target_qty) - float(current_fifo_total)
        
        logger.info(f"RECOUNT: {item.name} - FIFO total: {current_fifo_total}, target: {target_qty}, delta: {delta}")
        
        if delta == 0:
            # Update main item quantity to match FIFO
            item.quantity = float(current_fifo_total)
            db.session.add(item)
            return True, f"Recount complete: quantity confirmed at {current_fifo_total} {item.unit or 'units'}"
        
        elif delta > 0:
            # Need to add inventory
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=delta,
                change_type='recount',
                unit=item.unit or 'count',
                notes=notes or f"Recount adjustment: +{delta}",
                cost_per_unit=item.cost_per_unit or 0.0,
                created_by=created_by,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days
            )
            
            if success:
                item.quantity = float(target_qty)
                db.session.add(item)
                return True, f"Recount complete: added {delta} {item.unit or 'units'}, new total: {target_qty}"
            else:
                return False, f"Recount failed during addition: {error}"
        
        else:
            # Need to remove inventory (delta is negative)
            deduction_qty = abs(delta)
            success, error_msg = _handle_deductive_operation_internal(
                item_id=item.id,
                quantity=deduction_qty,
                change_type='recount',
                notes=notes or f"Recount adjustment: -{deduction_qty}",
                created_by=created_by
            )
            
            if success:
                item.quantity = float(target_qty)
                db.session.add(item)
                return True, f"Recount complete: removed {deduction_qty} {item.unit or 'units'}, new total: {target_qty}"
            else:
                return False, f"Recount failed during deduction: {error_msg}"
                
    except Exception as e:
        logger.error(f"RECOUNT ERROR: {str(e)}")
        return False, str(e)
