from models import ProductInventory, db
from sqlalchemy import and_

def get_fifo_inventory():
    """
    Gets all active FIFO inventory entries ordered by timestamp.
    """
    return ProductInventory.query.filter(
        ProductInventory.quantity > 0
    ).order_by(ProductInventory.timestamp.asc()).all()

def deduct_product_fifo(product_id, variant, unit, quantity_requested):
    """
    Deducts inventory from the oldest entries using FIFO logic.
    Returns a list of (history_id, quantity_deducted) pairs.
    """
    remaining = quantity_requested
    used_entries = []

    # Get valid inventory entries ordered by timestamp
    inventory_rows = InventoryHistory.query.filter(
        and_(
            ProductInventory.product_id == product_id,
            ProductInventory.variant == variant,
            ProductInventory.unit == unit,
            ProductInventory.quantity > 0
        )
    ).order_by(ProductInventory.timestamp.asc()).all()

    for row in inventory_rows:
        if remaining <= 0:
            break

        deduction = min(row.remaining_quantity or row.quantity_change, remaining)
        row.remaining_quantity = (row.remaining_quantity or row.quantity_change) - deduction
        remaining -= deduction
        used_entries.append((row.id, deduction))

    db.session.commit()
    return used_entries