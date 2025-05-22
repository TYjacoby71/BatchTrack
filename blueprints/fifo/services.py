from models import InventoryHistory, db
from sqlalchemy import and_, desc
from datetime import datetime

def get_fifo_entries(inventory_item_id):
    """Get all FIFO entries for an item with remaining quantity"""
    return InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

def deduct_fifo(inventory_item_id, quantity, change_type, notes, batch_id=None, created_by=None):
    """
    Deducts quantity using FIFO logic, returns deduction plan
    Args:
        inventory_item_id: ID of inventory item
        quantity: Amount to deduct
        change_type: Type of change (batch, spoil, etc)
        notes: Description of change
        batch_id: Optional batch ID for attribution
    """
    from models import InventoryItem
    
    remaining = quantity
    deduction_plan = []
    inventory_item = InventoryItem.query.get(inventory_item_id)

    if not inventory_item:
        return False, []

    fifo_entries = get_fifo_entries(inventory_item_id)

    for entry in fifo_entries:
        if remaining <= 0:
            break

        deduction = min(entry.remaining_quantity, remaining)
        remaining -= deduction

        deduction_plan.append((entry.id, deduction, entry.unit_cost))

    if remaining > 0:
        return False, []

    # Execute deductions and update inventory
    total_deducted = 0
    for entry_id, deduct_amount, unit_cost in deduction_plan:
        entry = InventoryHistory.query.get(entry_id)
        entry.remaining_quantity -= deduct_amount
        total_deducted += deduct_amount
        
        # Create history entry for deduction
        history = InventoryHistory(
            inventory_item_id=inventory_item_id,
            change_type=change_type,
            quantity_change=-deduct_amount,
            remaining_quantity=0,
            fifo_reference_id=entry_id,
            unit_cost=unit_cost,
            note=f"{notes} (From FIFO #{entry_id})",
            used_for_batch_id=batch_id,
            quantity_used=deduct_amount,
            created_by=created_by
        )
        db.session.add(history)

    # Verify FIFO matches inventory
    total_remaining = sum(entry.remaining_quantity for entry in get_fifo_entries(inventory_item_id))
    inventory_item.quantity = total_remaining
    db.session.add(inventory_item)

    return True, deduction_plan

def recount_fifo(inventory_item_id, new_quantity, note, user_id):
    """
    Handles recounts with proper FIFO integrity and expiration tracking
    """
    from models import InventoryItem
    from datetime import datetime, timedelta

    item = InventoryItem.query.get(inventory_item_id)
    current_entries = get_fifo_entries(inventory_item_id)
    current_total = sum(entry.remaining_quantity for entry in current_entries)

    difference = new_quantity - current_total

    if difference == 0:
        return True

    # Handle reduction in quantity
    if difference < 0:
        success, deductions = deduct_fifo(inventory_item_id, abs(difference), 'recount', note)
        if not success:
            return False

        # Create separate history entries for each FIFO deduction
        for entry_id, deduct_amount, unit_cost in deductions:
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='recount',
                quantity_change=-deduct_amount,
                remaining_quantity=0,
                fifo_reference_id=entry_id,
                unit_cost=unit_cost,
                note=f"{note} (From FIFO #{entry_id})",
                created_by=user_id,
                quantity_used=deduct_amount
            )
            db.session.add(history)

    # Handle increase in quantity    
    else:
        # Get all FIFO entries ordered by newest first that aren't at capacity
        unfilled_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity < InventoryHistory.quantity_change,
                InventoryHistory.quantity_change > 0  # Only get FIFO storage entries
            )
        ).order_by(InventoryHistory.timestamp.desc()).all()

        remaining_to_add = difference
        
        # First try to fill existing FIFO entries
        for entry in unfilled_entries:
            if remaining_to_add <= 0:
                break
                
            available_capacity = entry.quantity_change - entry.remaining_quantity
            fill_amount = min(available_capacity, remaining_to_add)
            
            if fill_amount > 0:
                # Log the recount but don't create new FIFO entry
                history = InventoryHistory(
                    inventory_item_id=inventory_item_id,
                    change_type='recount',
                    quantity_change=fill_amount,
                    remaining_quantity=0,  # Not a FIFO entry
                    fifo_reference_id=entry.id,
                    note=f"Recount restored to FIFO entry #{entry.id}",
                    created_by=user_id,
                    quantity_used=0
                )
                db.session.add(history)
                
                # Update the original FIFO entry
                entry.remaining_quantity += fill_amount
                remaining_to_add -= fill_amount

        # Only create new FIFO entry if we couldn't fill existing ones
        if remaining_to_add > 0:
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='restock',  # Use restock type for new FIFO entries
                quantity_change=remaining_to_add,
                remaining_quantity=remaining_to_add,
                note=f"New stock from recount after filling existing FIFO entries",
                created_by=user_id,
                quantity_used=0,
                timestamp=datetime.now()
            )
            db.session.add(history)

    db.session.commit()
    return True


def update_fifo_perishable_status(inventory_item_id, shelf_life_days):
    """Updates perishable status for all FIFO entries with remaining quantity"""
    from datetime import datetime, timedelta
    entries = InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).all()

    expiration_date = datetime.utcnow() + timedelta(days=shelf_life_days)
    for entry in entries:
        entry.is_perishable = True
        entry.shelf_life_days = shelf_life_days
        entry.expiration_date = expiration_date