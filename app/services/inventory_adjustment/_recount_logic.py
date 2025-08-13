import logging
from app.models import db, InventoryItem

logger = logging.getLogger(__name__)


def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """
    DUMB recount handler - calculates delta and delegates to canonical service.

    This handler is "dumb" about FIFO logic. It only:
    1. Gets current FIFO total from FIFO service
    2. Calculates delta
    3. Delegates back to process_inventory_adjustment with proper change_type

    The canonical service handles all FIFO orchestration.
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

        # Delegate to canonical service based on delta direction
        if delta > 0:
            # Need to add inventory - use restock change type
            from ._core import process_inventory_adjustment
            return process_inventory_adjustment(
                item_id=item_id,
                quantity=delta,
                change_type='restock',
                unit=getattr(item, 'unit', 'count'),
                notes=f"{notes or 'Recount increase'} - Added {delta}",
                created_by=created_by
            )
        else:
            # Need to deduct inventory - use recount change type for deduction
            from ._core import process_inventory_adjustment
            return process_inventory_adjustment(
                item_id=item_id,
                quantity=abs(delta),
                change_type='recount_deduction',
                unit=getattr(item, 'unit', 'count'),
                notes=f"{notes or 'Recount decrease'} - Deducted {abs(delta)}",
                created_by=created_by
            )

    except Exception as e:
        db.session.rollback()
        logger.error(f"RECOUNT ERROR: {str(e)}")
        raise e