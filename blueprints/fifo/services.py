
from models import InventoryHistory, db
from sqlalchemy import and_

def deduct_fifo(inventory_item_id, quantity_requested, source_type, source_reference):
    """
    Deducts inventory using FIFO logic
    source_type: batch, manual, spoilage etc
    source_reference: batch code or description
    """
    remaining = quantity_requested
    deduction_records = []

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

        history = InventoryHistory(
            inventory_item_id=inventory_item_id,
            change_type=source_type,
            quantity_change=-deduction,
            source=source_reference,
            source_fifo_id=entry.id,
            unit_cost=entry.unit_cost,
            quantity_used=deduction  # Add required quantity_used field
        )
        db.session.add(history)
        deduction_records.append(history)

    if remaining > 0:
        return None

    db.session.commit()
    return deduction_records

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
