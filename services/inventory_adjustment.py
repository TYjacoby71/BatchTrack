
from models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from services.conversion_wrapper import safe_convert
from blueprints.fifo.services import deduct_fifo

def process_inventory_adjustment(
    item_id,
    quantity,
    change_type,
    unit,
    notes='',
    batch_id=None,
    created_by=None,
    cost_override=None,
):
    """
    Centralized inventory adjustment logic for use in both manual adjustments and batch deductions
    """
    item = InventoryItem.query.get_or_404(item_id)

    # Convert units if needed (except for containers)
    if item.type != 'container' and unit != item.unit:
        conversion = safe_convert(quantity, unit, item.unit, ingredient_id=item.id)
        if not conversion['ok']:
            raise ValueError(conversion['error'])
        quantity = conversion['result']['converted_value']

    # Determine quantity change
    if change_type == 'recount':
        qty_change = quantity - item.quantity
    elif change_type in ['spoil', 'trash']:
        qty_change = -abs(quantity)
    else:
        qty_change = quantity

    # Handle expiration
    expiration_date = None
    if change_type == 'restock' and item.is_perishable and item.shelf_life_days:
        expiration_date = datetime.utcnow().date() + timedelta(days=item.shelf_life_days)

    # Get cost
    cost_per_unit = (
        cost_override if cost_override is not None
        else item.cost_per_unit if change_type not in ['spoil', 'trash', 'recount']
        else None
    )

    # Deductions
    if qty_change < 0:
        success, deductions = deduct_fifo(item.id, abs(qty_change), change_type, notes)
        if not success:
            raise ValueError("Insufficient FIFO stock")

        for entry_id, deduction_amount, _ in deductions:
            # Show clearer description for batch cancellations
            used_for_note = "canceled" if change_type == 'refunded' and batch_id else notes
            
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type=change_type,
                quantity_change=-deduction_amount,
                fifo_reference_id=entry_id,
                unit_cost=cost_per_unit,
                note=f"{used_for_note} (From FIFO #{entry_id})",
                created_by=created_by,
                quantity_used=deduction_amount,
                used_for_batch_id=batch_id
            )
            db.session.add(history)
        item.quantity += qty_change

    else:
        # Handle credits/refunds by finding original FIFO entries to credit back to
        if change_type == 'refunded' and batch_id:
            # Find the original deduction entries for this batch
            original_deductions = InventoryHistory.query.filter(
                InventoryHistory.inventory_item_id == item.id,
                InventoryHistory.used_for_batch_id == batch_id,
                InventoryHistory.quantity_change < 0,
                InventoryHistory.fifo_reference_id.isnot(None)
            ).order_by(InventoryHistory.timestamp.desc()).all()
            
            remaining_to_credit = qty_change
            
            # Credit back to the original FIFO entries
            for deduction in original_deductions:
                if remaining_to_credit <= 0:
                    break
                    
                original_fifo_entry = InventoryHistory.query.get(deduction.fifo_reference_id)
                if original_fifo_entry:
                    credit_amount = min(remaining_to_credit, abs(deduction.quantity_change))
                    
                    # Credit back to the original FIFO entry's remaining quantity
                    original_fifo_entry.remaining_quantity += credit_amount
                    remaining_to_credit -= credit_amount
                    
                    # Create credit history entry
                    credit_history = InventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,
                        quantity_change=credit_amount,
                        remaining_quantity=0,  # Credits don't create new FIFO entries
                        unit_cost=cost_per_unit,
                        fifo_reference_id=original_fifo_entry.id,  # Reference the original FIFO entry
                        note=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                        created_by=created_by,
                        quantity_used=0,
                        used_for_batch_id=batch_id
                    )
                    db.session.add(credit_history)
            
            # If there's still quantity to credit (shouldn't happen in normal cases)
            if remaining_to_credit > 0:
                # Create new FIFO entry for any excess
                excess_history = InventoryHistory(
                    inventory_item_id=item.id,
                    change_type='restock',  # Treat excess as new stock
                    quantity_change=remaining_to_credit,
                    remaining_quantity=remaining_to_credit,
                    unit_cost=cost_per_unit,
                    note=f"{notes} (Excess credit - no original FIFO found)",
                    created_by=created_by,
                    quantity_used=0,
                    expiration_date=expiration_date,
                    used_for_batch_id=batch_id
                )
                db.session.add(excess_history)
        else:
            # Regular additions (restock or recount or adjustment up)
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type=change_type,
                quantity_change=qty_change,
                remaining_quantity=qty_change if change_type in ['restock', 'finished_batch'] else None,
                unit_cost=cost_per_unit,
                note=notes,
                quantity_used=0,
                created_by=created_by,
                expiration_date=expiration_date,
                used_for_batch_id=batch_id if change_type not in ['restock'] else None  # Track batch for finished_batch
            )
            db.session.add(history)
        
        item.quantity += qty_change

    db.session.commit()
    return True
