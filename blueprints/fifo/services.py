
from models import InventoryHistory, db
from sqlalchemy import and_

def deduct_fifo(inventory_item_id, quantity_requested, source_type, source_reference):
    """
    Plans FIFO deduction without modifying inventory
    Returns: tuple(success, list of (entry_id, deduction_amount) tuples)
    """
    remaining = quantity_requested
    deduction_plan = []

    fifo_entries = InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

    for entry in fifo_entries:
        if remaining <= 0:
            break

        deduction = min(entry.remaining_quantity, remaining)
        entry.remaining_quantity -= deduction
        remaining -= deduction

        deduction_plan.append((entry.id, deduction, entry.unit_cost))
        
    if remaining > 0:
        return False, []

    return True, deduction_plan

def get_fifo_entries(inventory_item_id):
    return InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

def recount_fifo(inventory_item_id, new_quantity, note):
    current_total = db.session.query(db.func.sum(InventoryHistory.remaining_quantity))\
        .filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).scalar() or 0

    difference = new_quantity - current_total
    
    if difference > 0:
        oldest_entry = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).order_by(InventoryHistory.timestamp.asc()).first()

        history = InventoryHistory(
            inventory_item_id=inventory_item_id,
            change_type='recount',
            quantity_change=difference,
            remaining_quantity=difference,
            credited_to_fifo_id=oldest_entry.id if oldest_entry else None,
            note=note
        )
        db.session.add(history)
    else:
        deduct_fifo(inventory_item_id, abs(difference), 'recount', note)

    db.session.commit()
