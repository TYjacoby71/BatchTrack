
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
        # Get the emptied events in order by timestamp (oldest first)
        emptied_events = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity == 0,
                InventoryHistory.quantity_change > 0  # Original addition events
            )
        ).order_by(InventoryHistory.timestamp.asc()).all()

        remaining_credit = difference
        for event in emptied_events:
            if remaining_credit <= 0:
                break

            original_quantity = event.quantity_change
            credit_amount = min(remaining_credit, original_quantity)
            
            # Create recount history entry crediting this event
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='recount',
                quantity_change=credit_amount,
                remaining_quantity=credit_amount,
                credited_to_fifo_id=event.id,
                note=f"{note} (credited to event {event.id})",
                unit_cost=event.unit_cost,  # Use the same unit cost
                created_by=event.created_by,  # Copy the creator
                source=f"Recount credit to event {event.id}"
            )
            # Update the remaining quantity of the credited event
            event.remaining_quantity = credit_amount
            db.session.add(history)
            
            remaining_credit -= credit_amount

        # If there's still remaining credit with no events to credit to
        if remaining_credit > 0:
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='recount',
                quantity_change=remaining_credit,
                remaining_quantity=remaining_credit,
                note=f"{note} (new stock)"
            )
            db.session.add(history)
    else:
        deduct_fifo(inventory_item_id, abs(difference), 'recount', note)

    db.session.commit()
