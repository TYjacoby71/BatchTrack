"""
Special Operations Handler

Handles special inventory operations that don't follow standard FIFO patterns:
- Cost override operations
- Unit conversion operations
"""

import logging
from app.models import db
from app.utils.fifo_generator import generate_fifo_code # Moved to module level import
from ._fifo_ops import create_new_fifo_lot # Kept for local use within this file
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

    Recount logic:
    1. Calculate delta between current and target quantity
    2. If negative delta: deduct from existing lots (FIFO order), zero remaining if needed
    3. If positive delta: fill existing lots to capacity, create new lot for overflow
    4. Always set item quantity to target regardless of FIFO constraints

    Returns (success, message) - core will handle the absolute quantity setting for recounts
    """
    try:
        from app.models import UnifiedInventoryHistory, InventoryLot
        # from ._fifo_ops import create_new_fifo_lot # This import is now handled at the module level
        # from sqlalchemy import and_ # This import is now handled at the module level

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

        # Note: Individual lot adjustments will create their own history entries
        # No need for a main recount entry as the lot-specific entries provide full audit trail

        # Special-case: recount to zero must drain ALL lots regardless of desync
        if target_qty == 0:
            logger.info(f"RECOUNT: Target is zero; draining all lots for item {item.id}")
            existing_lots = InventoryLot.query.filter(
                and_(
                    InventoryLot.inventory_item_id == item.id,
                    InventoryLot.remaining_quantity > 0
                )
            ).order_by(InventoryLot.received_date.asc()).all()

            for lot in existing_lots:
                deducted = lot.remaining_quantity
                lot.remaining_quantity = 0.0

                # Generate proper recount event FIFO code (not creating lot, so is_lot_creation=False)
                recount_fifo_code = generate_fifo_code('recount', item.id, is_lot_creation=False)

                deduction_entry = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=-deducted,
                    remaining_quantity=None,  # N/A - this is an event record
                    unit=lot.unit,
                    unit_cost=lot.unit_cost,
                    fifo_code=recount_fifo_code,  # Use generated recount event code
                    notes=f"Recount to zero: drained lot {lot.fifo_code}",
                    created_by=created_by,
                    affected_lot_id=lot.id,
                    organization_id=item.organization_id
                )
                db.session.add(deduction_entry)

            # Core will set item.quantity = target_qty (0) afterwards
            logger.info(f"RECOUNT: All lots drained for item {item.id}")
            return True, f"Inventory recounted to {target_qty} and all lots drained"

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

                    # Generate proper recount event FIFO code (not creating lot, so is_lot_creation=False)
                    recount_fifo_code = generate_fifo_code('recount', item.id, is_lot_creation=False)

                    # Create deduction record using generated recount event code
                    deduction_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=-deducted,
                        remaining_quantity=None,  # N/A - this is an event record
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=recount_fifo_code,  # Use generated recount event code
                        notes=f"Recount deduction: -{deducted} from lot {lot.fifo_code}",
                        created_by=created_by,
                        affected_lot_id=lot.id,
                        organization_id=item.organization_id
                    )
                    db.session.add(deduction_entry)
                    logger.info(f"RECOUNT: Zeroed lot {lot.fifo_code} (was {deducted})")

                else:
                    # Partially deduct from this lot
                    lot.remaining_quantity -= remaining_to_deduct

                    # Generate proper recount event FIFO code (not creating lot, so is_lot_creation=False)
                    recount_fifo_code = generate_fifo_code('recount', item.id, is_lot_creation=False)

                    # Create deduction record using generated recount event code
                    deduction_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=-remaining_to_deduct,
                        remaining_quantity=None,  # N/A - this is an event record
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=recount_fifo_code,  # Use generated recount event code
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

                    # Generate proper recount event FIFO code (not creating lot, so is_lot_creation=False)
                    recount_fifo_code = generate_fifo_code('recount', item.id, is_lot_creation=False)

                    # Create addition record
                    addition_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # Use original change_type (recount)
                        quantity_change=fill_amount,
                        remaining_quantity=None,  # N/A - this is an event record
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        fifo_code=recount_fifo_code,  # Use generated recount event code
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

                add_success, add_message, new_lot_id = create_new_fifo_lot(
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

                # Generate proper recount event FIFO code (not creating lot, so is_lot_creation=False)
                recount_fifo_code = generate_fifo_code('recount', item.id, is_lot_creation=False)

                # Record the lot creation as an event linked to the lot
                overflow_event = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=remaining_to_add,
                    remaining_quantity=None,  # N/A - this is an event record
                    unit=item.unit or 'count',
                    unit_cost=item.cost_per_unit or 0.0,
                    fifo_code=recount_fifo_code,  # Use generated recount event code
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