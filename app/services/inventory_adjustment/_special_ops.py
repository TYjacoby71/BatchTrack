"""
Special Operations Handler

Handles special inventory operations that don't follow standard FIFO patterns:
- Cost override operations
- Unit conversion operations
"""

import logging
from app.models import db
from app.utils.fifo_generator import generate_fifo_code # Moved to module level import
from ._fifo_ops import create_new_fifo_lot, deduct_fifo_inventory # Kept for local use within this file and added deduct_fifo_inventory
from sqlalchemy import and_

logger = logging.getLogger(__name__)

def handle_cost_override(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
    """
    Handle cost override operations.

    This updates the cost_per_unit of an inventory item without affecting quantities.
    """
    try:
        if cost_override is None:
            return False, "Cost override operation requires a cost_override value"

        old_cost = item.cost_per_unit or 0.0
        item.cost_per_unit = float(cost_override)

        # Create history entry for audit trail
        from app.models import UnifiedInventoryHistory
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type='cost_override',
            quantity_delta=0.0,  # No quantity change
            quantity_after=item.quantity or 0.0,
            unit=item.unit or 'count',
            cost_per_unit=float(cost_override),
            notes=notes or f"Cost updated from {old_cost} to {cost_override}",
            created_by=created_by
        )

        db.session.add(item)
        db.session.add(history_entry)

        logger.info(f"COST OVERRIDE: Item {item.id} cost updated from {old_cost} to {cost_override}")
        return True, f"Cost updated from {old_cost} to {cost_override} per {item.unit or 'unit'}"

    except Exception as e:
        logger.error(f"COST OVERRIDE ERROR: {str(e)}")
        return False, str(e)

def handle_unit_conversion(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
    """
    Handle unit conversion operations.

    This is a placeholder for unit conversion logic.
    Currently not implemented as it requires complex conversion tables.
    """
    try:
        logger.warning(f"UNIT CONVERSION: Operation attempted on item {item.id} but not implemented")
        return False, "Unit conversion operations are not yet implemented"

    except Exception as e:
        logger.error(f"UNIT CONVERSION ERROR: {str(e)}")
        return False, str(e)

def handle_recount(item, quantity, change_type, notes=None, created_by=None, target_quantity=None, **kwargs):
    """
    Handle inventory recount with complete FIFO reconciliation.
    
    Four scenarios:
    1. Delta < 0: Deductive recount - remove inventory using FIFO
    2. Delta > 0 + existing lots can be refilled: Refill existing lots to capacity
    3. Delta > 0 + overflow needed: Refill existing lots + create new lot for overflow
    4. Delta = 0: Sync check only
    
    Each scenario generates proper recount event codes (RCN-xxx) with affected lot references.
    """
    try:
        from ._fifo_ops import deduct_fifo_inventory, create_new_fifo_lot, get_item_lots
        from app.models import UnifiedInventoryHistory
        from app.utils.fifo_generator import generate_fifo_code

        # For recounts, the target_quantity is the desired final quantity
        if target_quantity is None:
            target_quantity = quantity

        current_quantity = float(item.quantity)
        target_qty = float(target_quantity)
        delta = target_qty - current_quantity

        logger.info(f"RECOUNT: Item {item.id} current={current_quantity}, target={target_qty}, delta={delta}")

        recount_notes = f"Inventory recount: {current_quantity} -> {target_qty}"
        if notes:
            recount_notes += f" | {notes}"

        if delta == 0:
            # No change needed - just sync verification
            logger.info(f"RECOUNT: No adjustment needed for item {item.id}")
            return True, f"Inventory verified at {target_qty}"

        elif delta < 0:
            # SCENARIO 1: Deductive recount - remove inventory using FIFO
            abs_delta = abs(delta)
            logger.info(f"RECOUNT: Deducting {abs_delta} using FIFO deduction")

            success, message = deduct_fifo_inventory(
                item_id=item.id,
                quantity_to_deduct=abs_delta,
                change_type=change_type,  # This will create RCN-xxx codes in deduct_fifo_inventory
                notes=recount_notes,
                created_by=created_by
            )

            if not success:
                logger.warning(f"RECOUNT: FIFO deduction failed: {message}")
                return False, f"Recount deduction failed: {message}"

        else:
            # SCENARIOS 2 & 3: Additive recount - refill existing lots + handle overflow
            logger.info(f"RECOUNT: Adding {delta} - checking for refillable lots vs overflow")

            # Get existing lots that can be refilled (depleted lots)
            existing_lots = get_item_lots(item.id, active_only=False, order='desc')  # Newest first
            depleted_lots = [lot for lot in existing_lots if lot.remaining_quantity == 0]
            
            remaining_to_add = delta
            refilled_lots = 0

            # SCENARIO 2: Try to refill depleted lots first (newest first for recount)
            for lot in depleted_lots:
                if remaining_to_add <= 0:
                    break

                # Calculate how much we can refill this lot
                refill_capacity = lot.original_quantity
                refill_amount = min(remaining_to_add, refill_capacity)

                # Refill the lot
                lot.remaining_quantity = refill_amount
                db.session.add(lot)

                # Create recount event history for this refill
                recount_fifo_code = generate_fifo_code(change_type, item.id, is_lot_creation=False)
                
                refill_history = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=refill_amount,
                    unit=lot.unit,
                    unit_cost=lot.unit_cost,
                    notes=f"RECOUNT: Refilled {refill_amount} to lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                    created_by=created_by,
                    organization_id=item.organization_id,
                    affected_lot_id=lot.id,  # Links to the specific lot refilled
                    fifo_code=recount_fifo_code  # Recount event code (RCN-xxx)
                )
                db.session.add(refill_history)

                remaining_to_add -= refill_amount
                refilled_lots += 1
                
                logger.info(f"RECOUNT: Refilled {refill_amount} to lot {lot.id} ({lot.fifo_code})")

            # SCENARIO 3: Handle overflow if there's still quantity to add
            if remaining_to_add > 0:
                logger.info(f"RECOUNT: Creating overflow lot for remaining {remaining_to_add}")

                success, message, overflow_lot_id = create_new_fifo_lot(
                    item_id=item.id,
                    quantity=remaining_to_add,
                    change_type=change_type,
                    unit=item.unit or 'count',
                    notes=f"RECOUNT overflow: {remaining_to_add}" + (f" | {notes}" if notes else ""),
                    cost_per_unit=item.cost_per_unit or 0.0,
                    created_by=created_by
                )

                if not success:
                    return False, f"Failed to create recount overflow lot: {message}"

            # Log summary
            if refilled_lots > 0 and remaining_to_add > 0:
                summary_msg = f"Refilled {refilled_lots} lots, created overflow lot for {remaining_to_add}"
            elif refilled_lots > 0:
                summary_msg = f"Refilled {refilled_lots} existing lots"
            else:
                summary_msg = f"Created new lot for {delta}"

            logger.info(f"RECOUNT SUCCESS: {summary_msg}")

        # Return success - core will set the absolute quantity using target_quantity
        logger.info(f"RECOUNT COMPLETE: Item {item.id} FIFO reconciled for target {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"