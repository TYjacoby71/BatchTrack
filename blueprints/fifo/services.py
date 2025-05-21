
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

def deduct_fifo(inventory_item_id, quantity, change_type, notes):
    """
    Deducts quantity using FIFO logic, returns deduction plan
    """
    remaining = quantity
    deduction_plan = []

    fifo_entries = get_fifo_entries(inventory_item_id)
    
    for entry in fifo_entries:
        if remaining <= 0:
            break

        deduction = min(entry.remaining_quantity, remaining)
        remaining -= deduction

        deduction_plan.append((entry.id, deduction, entry.unit_cost))
        
    if remaining > 0:
        return False, []

    # Execute deductions
    for entry_id, deduct_amount, _ in deduction_plan:
        entry = InventoryHistory.query.get(entry_id)
        entry.remaining_quantity -= deduct_amount

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
    
    # Calculate expiration if item is perishable
    expiration_date = None
    if item.is_perishable and item.shelf_life_days:
        expiration_date = datetime.utcnow() + timedelta(days=item.shelf_life_days)
    
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
        # First, fill any remaining capacity in existing FIFO entries
        remaining_to_add = difference
        for entry in current_entries:
            if entry.remaining_quantity < entry.quantity_change:
                can_fill = entry.quantity_change - entry.remaining_quantity
                fill_amount = min(can_fill, remaining_to_add)
                # Create credited recount entry
                history = InventoryHistory(
                    inventory_item_id=inventory_item_id,
                    change_type='recount',
                    quantity_change=fill_amount,
                    remaining_quantity=0,
                    fifo_reference_id=entry.id,
                    note=f"Recount credit to FIFO entry #{entry.id}",
                    created_by=user_id,
                    quantity_used=fill_amount,
                    timestamp=datetime.utcnow()
                )
                db.session.add(history)
                entry.remaining_quantity += fill_amount
                remaining_to_add -= fill_amount
                
        # If there's still quantity to add, create new FIFO entry
        if remaining_to_add > 0:
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='recount',
                quantity_change=remaining_to_add,
                remaining_quantity=remaining_to_add,
                note=f"Recount yielded {remaining_to_add} more than could be filled in existing FIFO entries",
                created_by=user_id,
                quantity_used=0,
                timestamp=datetime.utcnow(),
                is_perishable=item.is_perishable,
                shelf_life_days=item.shelf_life_days,
                expiration_date=expiration_date
            )
            db.session.add(history)
        
    db.session.commit()
    return True

def reverse_recount(entry_id, user_id):
    """
    Reverses a recount entry if it hasn't been used
    """
    entry = InventoryHistory.query.get(entry_id)
    
    if not entry or entry.change_type != 'recount' or entry.remaining_quantity != entry.quantity_change:
        return False
        
    reversal = InventoryHistory(
        inventory_item_id=entry.inventory_item_id,
        change_type='recount',
        quantity_change=-entry.quantity_change,
        remaining_quantity=0,
        credited_to_fifo_id=entry.id,
        note=f'Reversal of recount #{entry.id}',
        created_by=user_id,
        quantity_used=abs(entry.quantity_change)
    )
    
    entry.remaining_quantity = 0
    db.session.add(reversal)
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
