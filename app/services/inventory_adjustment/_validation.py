
from app.models import InventoryItem, UnifiedInventoryHistory
from sqlalchemy import and_


def validate_inventory_fifo_sync(item_id, item_type=None):
    """Validate that inventory quantity matches FIFO totals"""
    import logging
    logger = logging.getLogger(__name__)
    
    item = InventoryItem.query.get(item_id)
    if not item:
        return False, "Item not found", 0, 0

    # Get sum of remaining quantities from FIFO entries
    fifo_entries = UnifiedInventoryHistory.query.filter(
        and_(
            UnifiedInventoryHistory.inventory_item_id == item_id,
            UnifiedInventoryHistory.remaining_quantity > 0
        )
    ).all()

    fifo_total = sum(float(entry.remaining_quantity) for entry in fifo_entries)
    inventory_qty = float(item.quantity)

    # Allow small floating point differences
    tolerance = 0.001
    is_valid = abs(inventory_qty - fifo_total) < tolerance

    if not is_valid:
        logger.error(f"FIFO SYNC MISMATCH for item {item_id} ({item.name}):")
        logger.error(f"  Item quantity: {inventory_qty}")
        logger.error(f"  FIFO total: {fifo_total}")
        logger.error(f"  Difference: {abs(inventory_qty - fifo_total)}")
        logger.error(f"  Active FIFO entries: {len(fifo_entries)}")
        
        # Log individual FIFO entries for debugging
        for i, entry in enumerate(fifo_entries):
            logger.error(f"    Entry {i+1}: {entry.remaining_quantity} ({entry.change_type}, {entry.timestamp})")
        
        error_msg = f"FIFO sync error: inventory={inventory_qty}, fifo_total={fifo_total}, diff={abs(inventory_qty - fifo_total)}"
        return False, error_msg, inventory_qty, fifo_total

    return True, None, inventory_qty, fifo_total
