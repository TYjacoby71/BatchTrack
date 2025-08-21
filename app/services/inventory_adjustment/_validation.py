
from app.models import InventoryItem, UnifiedInventoryHistory
from sqlalchemy import and_


def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    Validate that inventory quantity matches FIFO totals using proper InventoryLot model.
    This ensures the item.quantity field stays in sync with actual lot quantities.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from app.models.inventory_lot import InventoryLot
    from app.models import InventoryItem
    
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, "Item not found", 0, 0

    # Get all active lots for this item with proper organization scoping
    active_lots = InventoryLot.query.filter(
        and_(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.organization_id == item.organization_id,
            InventoryLot.remaining_quantity > 0
        )
    ).all()

    # Calculate total from actual lot quantities
    fifo_total = sum(float(lot.remaining_quantity) for lot in active_lots)
    inventory_qty = float(item.quantity or 0)

    # Allow small floating point differences (0.01 tolerance)
    tolerance = 0.01 = 0.001
    is_valid = abs(inventory_qty - fifo_total) < tolerance

    if not is_valid:
        logger.error(f"FIFO SYNC MISMATCH for item {item_id} ({item.name}):")
        logger.error(f"  Item quantity: {inventory_qty}")
        logger.error(f"  FIFO total: {fifo_total}")
        logger.error(f"  Difference: {abs(inventory_qty - fifo_total)}")
        logger.error(f"  Active FIFO lots: {len(lots)}")
        
        # Log individual FIFO lots for debugging
        for i, lot in enumerate(lots):
            logger.error(f"    Lot {i+1}: {lot.remaining_quantity} ({lot.source_type}, {lot.received_date})")
        
        error_msg = f"FIFO sync error: inventory={inventory_qty}, fifo_total={fifo_total}, diff={abs(inventory_qty - fifo_total)}"
        return False, error_msg, inventory_qty, fifo_total

    return True, None, inventory_qty, fifo_total
