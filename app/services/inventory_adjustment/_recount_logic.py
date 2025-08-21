
"""
Recount logic handler - handles inventory recounts (setting absolute quantities).
This handler calculates the difference and adjusts FIFO lots to match the target quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory, InventoryLot
from ._fifo_ops import _internal_add_fifo_entry_enhanced
from sqlalchemy import and_

logger = logging.getLogger(__name__)

def handle_recount(item, quantity, change_type, notes=None, created_by=None, target_quantity=None, **kwargs):
    """
    Handle inventory recount - set absolute quantity and reconcile FIFO lots.
    
    Recount logic:
    1. Calculate delta between current and target quantity
    2. If negative delta: deduct from existing lots (FIFO order), zero remaining if needed
    3. If positive delta: fill existing lots to capacity, create new lot for overflow
    4. Always set item quantity to target regardless of FIFO constraints
    
    Returns (success, message) - core will handle the absolute quantity setting for recounts
    """
    try:
        # For recounts, the target_quantity is the desired final quantity
        if target_quantity is None:
            target_quantity = quantity

        current_quantity = float(item.quantity)
        target_qty = float(target_quantity)
        delta = target_qty - current_quantity

        logger.info(f"RECOUNT: Item {item.id} current={current_quantity}, target={target_qty}, delta={delta}")

        # Create a recount history entry to document the change
        recount_notes = f"Inventory recount: {current_quantity} -> {target_qty}"
        if notes:
            recount_notes += f" | {notes}"

        # Create unified history entry for the recount
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=delta,
            remaining_quantity=0,  # Recount entries don't have remaining quantity
            unit=item.unit or 'count',
            unit_cost=item.cost_per_unit or 0.0,
            notes=recount_notes,
            created_by=created_by,
            organization_id=item.organization_id,
            fifo_code=f"RECOUNT-{item.id}-{target_qty}"
        )

        db.session.add(history_entry)

        if delta < 0:
            # Need to remove inventory - deduct from existing lots or zero them
            abs_delta = abs(delta)
            logger.info(f"RECOUNT: Removing {abs_delta} from existing lots")
            
            # Get all lots with remaining quantity (oldest first - FIFO)
            existing_lots = InventoryLot.query.filter(
                and_(
                    InventoryLot.inventory_item_id == item.id,
                    InventoryLot.remaining_quantity > 0
                )
            ).order_by(InventoryLot.received_date.asc()).all()
            
            remaining_to_deduct = abs_delta
            
            for lot in existing_lots:
                if remaining_to_deduct <= 0:
                    break
                    
                if lot.remaining_quantity <= remaining_to_deduct:
                    # Zero out this entire lot
                    deducted = lot.remaining_quantity
                    lot.remaining_quantity = 0.0
                    remaining_to_deduct -= deducted
                    
                    # Create deduction record
                    deduction_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=-deducted,
                        remaining_quantity=0,
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=lot.fifo_code,
                        notes=f"Recount deduction: zeroed lot {lot.fifo_code}",
                        created_by=created_by,
                        affected_lot_id=lot.id,
                        organization_id=item.organization_id
                    )
                    db.session.add(deduction_entry)
                    logger.info(f"RECOUNT: Zeroed lot {lot.fifo_code} (was {deducted})")
                    
                else:
                    # Partially deduct from this lot
                    lot.remaining_quantity -= remaining_to_deduct
                    
                    # Create deduction record
                    deduction_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=-remaining_to_deduct,
                        remaining_quantity=0,
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=lot.fifo_code,
                        notes=f"Recount deduction: -{remaining_to_deduct} from lot {lot.fifo_code}",
                        created_by=created_by,
                        affected_lot_id=lot.id,
                        organization_id=item.organization_id
                    )
                    db.session.add(deduction_entry)
                    logger.info(f"RECOUNT: Deducted {remaining_to_deduct} from lot {lot.fifo_code}")
                    remaining_to_deduct = 0
            
            # If we still have amount to deduct, it means we zeroed all lots
            # This is fine for recount - we just set quantity to target regardless
            if remaining_to_deduct > 0:
                logger.info(f"RECOUNT: Zeroed all lots, {remaining_to_deduct} units deducted beyond available FIFO")

        elif delta > 0:
            # Need to add inventory - fill existing lots first, then create new lot
            logger.info(f"RECOUNT: Adding {delta} to reconcile inventory")
            
            # Get all lots (including depleted ones) to see if we can fill them
            existing_lots = InventoryLot.query.filter(
                InventoryLot.inventory_item_id == item.id
            ).order_by(InventoryLot.received_date.asc()).all()
            
            remaining_to_add = delta
            
            # First, try to fill existing lots to their original capacity
            for lot in existing_lots:
                if remaining_to_add <= 0:
                    break
                    
                available_capacity = lot.original_quantity - lot.remaining_quantity
                if available_capacity > 0:
                    # This lot can be filled
                    fill_amount = min(available_capacity, remaining_to_add)
                    lot.remaining_quantity += fill_amount
                    remaining_to_add -= fill_amount
                    
                    # Create addition record
                    addition_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=fill_amount,
                        remaining_quantity=0,
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=lot.fifo_code,
                        notes=f"Recount refill: +{fill_amount} to lot {lot.fifo_code}",
                        created_by=created_by,
                        affected_lot_id=lot.id,
                        organization_id=item.organization_id
                    )
                    db.session.add(addition_entry)
                    logger.info(f"RECOUNT: Refilled {fill_amount} to lot {lot.fifo_code}")
            
            # If we still have quantity to add, create a new lot for the overflow
            if remaining_to_add > 0:
                logger.info(f"RECOUNT: Creating new lot for overflow: {remaining_to_add}")
                
                add_success, add_message, new_lot_id = _internal_add_fifo_entry_enhanced(
                    item_id=item.id,
                    quantity=remaining_to_add,
                    change_type=change_type,  # Use original change_type (recount)
                    unit=item.unit or 'count',
                    notes=f"Recount overflow: +{remaining_to_add}",
                    cost_per_unit=item.cost_per_unit or 0.0,
                    created_by=created_by
                )
                
                if not add_success:
                    return False, f"Failed to create recount overflow lot: {add_message}"

                # Record the lot creation as an event linked to the lot
                overflow_event = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=remaining_to_add,
                    remaining_quantity=0,
                    unit=item.unit or 'count',
                    unit_cost=item.cost_per_unit or 0.0,
                    fifo_code=None,
                    notes=f"Recount overflow lot created: +{remaining_to_add}",
                    created_by=created_by,
                    affected_lot_id=new_lot_id,
                    organization_id=item.organization_id
                )
                db.session.add(overflow_event)

        # Return success - core will set the absolute quantity using target_quantity
        logger.info(f"RECOUNT SUCCESS: Item {item.id} FIFO reconciled for target {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"
