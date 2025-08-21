
import logging
from app.models import db, InventoryItem
from ._fifo_ops import handle_restock, _handle_deductive_operation, calculate_current_fifo_total

logger = logging.getLogger(__name__)


def handle_recount_adjustment_clean(item, quantity, notes=None, created_by=None, **kwargs):
    """
    CLEAN recount handler that works directly with FIFO operations.
    
    This handler calculates the delta and directly calls the appropriate
    specialist function WITHOUT going back through the main dispatcher.
    """
    try:
        # Get current FIFO total from authoritative source
        current_fifo_total = calculate_current_fifo_total(item.id)
        target_qty = float(quantity or 0.0)

        # Calculate delta
        delta = target_qty - current_fifo_total

        logger.info(f"RECOUNT: {item.name} - FIFO total: {current_fifo_total}, target: {target_qty}, delta: {delta}")

        # No change needed
        if abs(delta) < 0.001:
            # Sync item.quantity to FIFO total for consistency
            item.quantity = current_fifo_total
            db.session.commit()
            return True, f"Inventory already at target quantity: {target_qty}"

        # Apply the delta directly using specialist functions
        if delta > 0:
            # Need to add inventory - call restock specialist directly
            success, message = handle_restock(
                item=item,
                quantity=delta,
                notes=f"{notes or 'Recount increase'} - Added {delta}",
                created_by=created_by
            )
            return success, message
        else:
            # Need to deduct inventory - call deductive operation directly
            success = _handle_deductive_operation(
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


# Keep the old function for backward compatibility during transition
def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """Legacy function - redirects to new clean handler"""
    item = InventoryItem.query.get(item_id)
    if not item:
        return False, "Item not found"
        
    return handle_recount_adjustment_clean(
        item=item,
        quantity=target_quantity,
        notes=notes,
        created_by=created_by
    )
