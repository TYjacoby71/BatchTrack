import logging
from app.models import db, InventoryItem
from ._fifo_ops import calculate_current_fifo_total
from ._additive_ops import handle_additive_operation
from ._deductive_ops import _handle_deductive_operation_internal

logger = logging.getLogger(__name__)


def handle_recount_adjustment_clean(item, quantity, notes=None, created_by=None, **kwargs):
    """
    CLEAN recount handler that works directly with FIFO operations.

    This handler calculates the delta and directly calls the appropriate
    specialist function WITHOUT going back through the main dispatcher.
    """
    try:
        # Get current FIFO total for comparison
        from ._fifo_ops import calculate_current_fifo_total
        fifo_total = calculate_current_fifo_total(item.id)
        delta = float(quantity or 0.0) - fifo_total

        logger.info(f"RECOUNT: {item.name} - FIFO total: {fifo_total}, target: {quantity}, delta: {delta}")

        # No change needed
        if abs(delta) < 0.001:
            # Sync item.quantity to FIFO total for consistency
            item.quantity = fifo_total
            db.session.commit()
            return True, f"Inventory already at target quantity: {quantity}"

        # Apply the delta directly using specialist functions
        if delta > 0:
            # Need to add inventory - call additive operation directly
            success, message = handle_additive_operation(
                item=item,
                quantity=delta,
                change_type='recount_increase',
                notes=f"{notes or 'Recount increase'} - Added {delta}",
                created_by=created_by
            )
            return success, message
        else:
            # Need to deduct inventory - call deductive operation directly
            success = _handle_deductive_operation_internal(
                item=item,
                quantity=abs(delta),
                change_type='recount_deduction',
                notes=f"{notes or 'Recount decrease'} - Deducted {abs(delta)}",
                created_by=created_by
            )

            if success:
                return True, f"Recount adjusted down by {abs(delta)}"
            else:
                return False, "Failed to apply recount deduction"

    except Exception as e:
        db.session.rollback()
        logger.error(f"RECOUNT ERROR: {str(e)}")
        return False, str(e)
"""
Recount Operations Handler

Handles recount operations that adjust inventory to match physical counts
"""

import logging
from app.models import db
from ._fifo_ops import _internal_add_fifo_entry_enhanced, _handle_deductive_operation_internal

logger = logging.getLogger(__name__)

def handle_recount(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle recount operations - adjust inventory to match physical count"""
    try:
        current_quantity = float(item.quantity)
        target_quantity = float(quantity)
        difference = target_quantity - current_quantity
        
        if abs(difference) < 0.001:  # No significant change
            return True, "No adjustment needed"
        
        if difference > 0:
            # Need to add inventory
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=difference,
                change_type='recount_addition',
                unit=getattr(item, 'unit', 'count'),
                notes=notes or f'Recount adjustment: +{difference}',
                cost_per_unit=item.cost_per_unit,
                created_by=created_by,
                **kwargs
            )
            if success:
                return True, f"Added {difference} {getattr(item, 'unit', 'units')} via recount"
            return False, error
        else:
            # Need to remove inventory
            success = _handle_deductive_operation_internal(
                item, abs(difference), 'recount_deduction', 
                notes or f'Recount adjustment: -{abs(difference)}', 
                created_by, **kwargs
            )
            if success:
                return True, f"Removed {abs(difference)} {getattr(item, 'unit', 'units')} via recount"
            return False, "Insufficient inventory for recount adjustment"
            
    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, str(e)
