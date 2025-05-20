
from models import InventoryHistory, db
from sqlalchemy import and_

def deduct_fifo(inventory_item_id, quantity_requested):
    """
    Deducts inventory using FIFO logic for any inventory type
    Returns a list of (history_id, quantity_deducted) pairs
    """
    remaining = quantity_requested
    used_entries = []

    # Get valid inventory entries ordered by timestamp
    inventory_rows = InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

    for row in inventory_rows:
        if remaining <= 0:
            break

        deduction = min(row.remaining_quantity or row.quantity_change, remaining)
        row.remaining_quantity = (row.remaining_quantity or row.quantity_change) - deduction
        remaining -= deduction
        used_entries.append((row.id, deduction))

    if remaining > 0:
        return None  # Not enough stock

    db.session.commit()
    return used_entries

def get_fifo_entries(inventory_item_id):
    """
    Gets all active FIFO inventory entries ordered by timestamp
    """
    return InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()
