
"""
Recount logic handler - handles inventory recounts (setting absolute quantities).
This handler calculates the difference and lets the core apply the change.
It should NEVER directly modify item.quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory
from ._fifo_ops import _internal_add_fifo_entry_enhanced, _handle_deductive_operation_internal

logger = logging.getLogger(__name__)

def handle_recount(item, quantity, change_type, notes=None, created_by=None, target_quantity=None, **kwargs):
    """
    Handle inventory recount - set absolute quantity.
    This is a special operation that calculates the difference between current and target,
    then returns success for the core to handle the absolute setting.
    
    Returns (success, message) - core will handle the absolute quantity setting for recounts
    """
    try:
        # For recounts, the target_quantity is the desired final quantity
        if target_quantity is None:
            target_quantity = quantity

        current_quantity = float(item.quantity)
        target_qty = float(target_quantity)
        difference = target_qty - current_quantity

        logger.info(f"RECOUNT: Item {item.id} current={current_quantity}, target={target_qty}, difference={difference}")

        # Create a recount history entry to document the change
        recount_notes = f"Inventory recount: {current_quantity} -> {target_qty}"
        if notes:
            recount_notes += f" | {notes}"

        # Create unified history entry for the recount
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=difference,
            remaining_quantity=0,  # Recount entries don't have remaining quantity
            unit=item.unit or 'count',
            unit_cost=item.cost_per_unit or 0.0,
            notes=recount_notes,
            created_by=created_by,
            organization_id=item.organization_id,
            fifo_code=f"RECOUNT-{item.id}-{target_qty}"
        )

        db.session.add(history_entry)

        if difference > 0:
            # Need to add inventory - create FIFO entry for the increase
            logger.info(f"RECOUNT: Adding {difference} to reconcile inventory")
            
            add_success, add_message = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=difference,
                change_type='recount_adjustment',
                unit=item.unit or 'count',
                notes=f"Recount adjustment: +{difference}",
                cost_per_unit=item.cost_per_unit or 0.0,
                created_by=created_by
            )
            
            if not add_success:
                return False, f"Failed to add recount adjustment: {add_message}"

        elif difference < 0:
            # Need to remove inventory - use FIFO deduction for the decrease
            logger.info(f"RECOUNT: Removing {abs(difference)} to reconcile inventory")
            
            remove_success, remove_message = _handle_deductive_operation_internal(
                item_id=item.id,
                quantity_to_deduct=abs(difference),
                change_type='recount_adjustment',
                notes=f"Recount adjustment: -{abs(difference)}",
                created_by=created_by
            )
            
            if not remove_success:
                return False, f"Failed to remove recount adjustment: {remove_message}"

        # Return success - core will set the absolute quantity
        logger.info(f"RECOUNT SUCCESS: Item {item.id} will be set to {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"
