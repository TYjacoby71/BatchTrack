import logging
from app.models import db, InventoryItem

logger = logging.getLogger(__name__)


def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """
    SMART recount handler - handles overflow by creating new lots with recount change_type.
    
    For recount increases:
    1. Gets addition plan from FIFO service to refill existing lots
    2. Creates overflow lots with change_type='recount' for any remaining quantity
    3. All recount entries show change_type='recount' regardless of operation type
    
    For recount decreases:
    1. Uses deduction plan from FIFO service
    """
    try:
        # Get the item
        item = InventoryItem.query.get(item_id)
        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        # Get current FIFO total from authoritative source
        from ._fifo_ops import calculate_current_fifo_total
        current_fifo_total = calculate_current_fifo_total(item_id)
        target_qty = float(target_quantity or 0.0)

        # Calculate delta
        delta = target_qty - current_fifo_total

        print(f"RECOUNT: {item.name} - FIFO total: {current_fifo_total}, target: {target_qty}, delta: {delta}")

        # No change needed
        if abs(delta) < 0.001:
            # Still sync item.quantity to FIFO total for consistency
            item.quantity = current_fifo_total
            db.session.commit()
            return True

        # Handle recount increase (need to add inventory)
        if delta > 0:
            return _handle_recount_increase(item_id, delta, notes, created_by)
        else:
            # Handle recount decrease (need to deduct inventory)
            from ._core import process_inventory_adjustment
            return process_inventory_adjustment(
                item_id=item_id,
                quantity=abs(delta),
                change_type='recount',
                unit=getattr(item, 'unit', 'count'),
                notes=f"{notes or 'Recount decrease'} - Deducted {abs(delta)}",
                created_by=created_by
            )

    except Exception as e:
        db.session.rollback()
        logger.error(f"RECOUNT ERROR: {str(e)}")
        raise e


def _handle_recount_increase(item_id, delta_quantity, notes, created_by):
    """
    Handle recount increases by:
    1. First refilling existing lots using FIFO addition plan
    2. Creating new lots with change_type='recount' for overflow
    """
    try:
        from ._fifo_ops import (
            _calculate_addition_plan_internal,
            _execute_addition_plan_internal, 
            _record_addition_plan_internal,
            _internal_add_fifo_entry_enhanced,
            calculate_current_fifo_total
        )
        
        item = db.session.get(InventoryItem, item_id)
        final_unit = getattr(item, 'unit', 'count')
        
        # Get addition plan from FIFO service to refill existing lots
        addition_plan, remaining_overflow = _calculate_addition_plan_internal(
            item_id, delta_quantity, 'recount'
        )
        
        # Step 1: Refill existing lots if there's an addition plan
        if addition_plan:
            # Execute the addition plan
            success, error = _execute_addition_plan_internal(addition_plan, item_id)
            if not success:
                logger.error(f"Addition plan execution failed: {error}")
                return False
            
            # Record audit trail for additions to existing lots
            success = _record_addition_plan_internal(
                item_id, addition_plan, 'recount', 
                f"{notes or 'Recount refill'} - Refilled existing lots", 
                created_by=created_by
            )
            if not success:
                logger.error(f"Addition plan recording failed")
                return False
        
        # Step 2: Create new lot for overflow with change_type='recount'
        if remaining_overflow > 0:
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item_id,
                quantity=remaining_overflow,
                change_type='recount',  # Overflow lots use recount change_type
                unit=final_unit,
                notes=f"{notes or 'Recount overflow'} - New lot for overflow {remaining_overflow}",
                cost_per_unit=item.cost_per_unit,
                created_by=created_by
            )
            
            if not success:
                logger.error(f"Overflow lot creation failed: {error}")
                return False
        
        # Step 3: Sync item quantity to FIFO total
        current_fifo_total = calculate_current_fifo_total(item_id)
        item.quantity = current_fifo_total
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error in recount increase: {str(e)}")
        db.session.rollback()
        return False