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