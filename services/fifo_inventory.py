
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
    Deducts inventory from the oldest batches using FIFO logic.
    Returns a list of (batch_id, quantity_deducted) pairs.
    """
    remaining = quantity_requested
    used_batches = []

    inventory_rows = ProductInventory.query.filter(
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

        deduction = min(row.quantity, remaining)
        row.quantity -= deduction
        remaining -= deduction
        used_batches.append((row.batch_id, deduction))

    db.session.commit()
    return used_batches
