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
    Handle inventory recount - set absolute quantity and reconcile FIFO lots.

    This function now delegates to standard FIFO operations instead of manually creating history entries.

    Returns (success, message) - core will handle the absolute quantity setting for recounts
    """
    try:
        from ._fifo_ops import deduct_fifo_inventory

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

        if delta < 0:
            # Need to remove inventory - use standard FIFO deduction
            abs_delta = abs(delta)
            logger.info(f"RECOUNT: Deducting {abs_delta} using standard FIFO operations")

            success, message = deduct_fifo_inventory(
                item_id=item.id,
                quantity_to_deduct=abs_delta,
                change_type=change_type,
                notes=recount_notes,
                created_by=created_by
            )

            if not success:
                logger.warning(f"RECOUNT: FIFO deduction failed, but continuing with absolute recount: {message}")
                # For recount, we continue even if FIFO fails - we'll set absolute quantity

        elif delta > 0:
            # Need to add inventory - use standard lot creation
            logger.info(f"RECOUNT: Adding {delta} using standard FIFO operations")

            success, message, new_lot_id = create_new_fifo_lot(
                item_id=item.id,
                quantity=delta,
                change_type=change_type,
                unit=item.unit or 'count',
                notes=recount_notes,
                cost_per_unit=item.cost_per_unit or 0.0,
                created_by=created_by
            )

            if not success:
                return False, f"Failed to create recount lot: {message}"

        # Return success - core will set the absolute quantity using target_quantity
        logger.info(f"RECOUNT SUCCESS: Item {item.id} FIFO reconciled for target {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"