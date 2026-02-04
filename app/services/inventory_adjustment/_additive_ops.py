"""
Additive operations handler - operations that increase inventory quantity.
These handlers calculate what needs to happen and return deltas.
They should NEVER directly modify item.quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory
from app.services.quantity_base import from_base_quantity, sync_lot_quantities_from_base
from ._fifo_ops import create_new_fifo_lot

logger = logging.getLogger(__name__)

# Define operation groups and their processing logic
ADDITIVE_OPERATION_GROUPS = {
    'lot_creation': {
        'operations': ['restock', 'manual_addition', 'finished_batch'],
        'description': 'Operations that create new lots',
        'creates_lot': True,
        'creates_history': True
    },
    'lot_crediting': {
        'operations': ['returned', 'refunded', 'release_reservation'],
        'description': 'Operations that credit back to existing FIFO lots',
        'creates_lot': False,  # Credits existing lots via FIFO
        'creates_history': True
    }
}

def _get_operation_group(change_type):
    """Get the operation group for a given change type"""
    for group_name, group_config in ADDITIVE_OPERATION_GROUPS.items():
        if change_type in group_config['operations']:
            return group_name, group_config
    return None, None

def _universal_additive_handler(item, quantity, quantity_base, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, unit=None, batch_id=None, **kwargs):
    """
    Universal handler for all additive operations.
    Processes operations based on their group classification.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"{change_type.upper()}: Processing {quantity} for item {item.id}")

        # Get operation group and configuration
        group_name, group_config = _get_operation_group(change_type)
        if not group_config:
            return False, f"Unknown additive operation: {change_type}", 0

        logger.info(f"{change_type.upper()}: Classified as {group_name} operation")

        # Use item's unit if not specified in kwargs
        unit = unit or item.unit or 'count'

        # Use provided cost or item's default cost
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        if quantity is None or quantity_base is None:
            return False, f"Invalid quantity: {quantity}", 0
        quantity_delta = float(quantity)
        quantity_delta_base = int(quantity_base)

        if group_name == 'lot_creation':
            # Operations that create new lots (restock, manual_addition, finished_batch)
            success, message, lot_id = _handle_lot_creation_operation(
                item=item,
                quantity=quantity,
                quantity_base=quantity_base,
                change_type=change_type,
                notes=notes,
                created_by=created_by,
                cost_override=cost_override,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days,
                operation_unit=unit,
                batch_id=batch_id  # Pass batch_id here
            )

        elif group_name == 'lot_crediting':
            # Operations that credit back to existing lots (returned, refunded, release_reservation)
            success, message, lot_id = _handle_lot_crediting_operation(
                item,
                quantity,
                quantity_base,
                change_type,
                unit,
                notes,
                final_cost,
                created_by,
                batch_id=batch_id,
                **kwargs # Pass batch_id here
            )

        else:
            return False, f"Unhandled operation group: {group_name}", 0

        if not success:
            return False, message, 0

        # Generate appropriate success message
        action_messages = {
            'restock': f"Restocked {quantity} {unit}",
            'manual_addition': f"Manual addition of {quantity} {unit}",
            'finished_batch': f"Finished batch added {quantity} {unit}",
            'returned': f"Returned {quantity} {unit} to inventory",
            'refunded': f"Refunded {quantity} {unit} added to inventory",
            'release_reservation': f"Released reservation, credited {quantity} {unit}"
        }

        success_message = action_messages.get(change_type, f"{change_type.replace('_', ' ').title()} added {quantity} {unit}")

        logger.info(f"{change_type.upper()} SUCCESS: Will increase item {item.id} by {quantity_delta}")
        return True, success_message, quantity_delta, quantity_delta_base

    except Exception as e:
        logger.error(f"Error in {change_type} operation: {str(e)}")
        return False, f"{change_type.replace('_', ' ').title()} failed: {str(e)}", 0



def _handle_lot_creation_operation(item, quantity, quantity_base, change_type, notes, created_by, custom_expiration_date, custom_shelf_life_days, operation_unit, batch_id=None, cost_override=None):
    """
    Handle operations that create new lots (restock, returns, etc.)
    Returns (success, message, quantity_delta)
    """
    try:
        logger.info(f"LOT_CREATION: Adding {quantity} to item {item.id}")

        unit = operation_unit or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Create the FIFO lot
        success, message, lot_id = create_new_fifo_lot(
            item_id=item.id,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type=change_type,
            unit=unit,
            notes=notes or f"{change_type.title()} operation",
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            batch_id=batch_id # Pass batch_id here
        )

        if not success:
            return False, f"Failed to create lot: {message}", 0

        # Return the quantity delta for core to apply
        if quantity is None or quantity_base is None: # Added check here to handle potential None quantity passed to this function
            return False, f"Invalid quantity: {quantity}", 0
        quantity_delta = float(quantity)
        logger.info(f"LOT_CREATION SUCCESS: Will add {quantity_delta} to item {item.id}")

        return True, f"{change_type.title()} of {quantity} {unit} completed", quantity_delta

    except Exception as e:
        logger.error(f"Error in lot creation operation: {str(e)}")
        return False, f"Lot creation failed: {str(e)}", 0

def _handle_lot_crediting_operation(item, quantity, quantity_base, change_type, unit, notes, final_cost, created_by, batch_id=None, customer=None, order_id=None, **kwargs):
    """Handle operations that credit back to existing FIFO lots"""
    from app.models.inventory_lot import InventoryLot
    from app.utils.inventory_event_code_generator import generate_inventory_event_code
    from sqlalchemy import and_

    logger.info(f"LOT_CREDITING: Processing {change_type} credit operation for {quantity} {unit}")

    try:
        # For refunds and returns, we want to credit back to existing lots using FIFO order (oldest first)
        # This simulates returning inventory to the lots it originally came from

        # Get depleted or partially depleted lots ordered by FIFO (oldest received first)
        lots_to_credit = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item.id,
                InventoryLot.organization_id == item.organization_id,
                InventoryLot.remaining_quantity_base < InventoryLot.original_quantity_base  # Lots that have been consumed from
            )
        ).order_by(InventoryLot.received_date.asc()).all()

        remaining_to_credit_base = int(quantity_base)
        lots_credited = 0

        # Credit back to existing lots first (FIFO order)
        for lot in lots_to_credit:
            if remaining_to_credit_base <= 0:
                break

            # Calculate how much space is available in this lot
            space_available_base = int(lot.original_quantity_base) - int(lot.remaining_quantity_base)

            if space_available_base > 0:
                # Credit back up to the available space
                credit_amount_base = min(space_available_base, remaining_to_credit_base)
                lot.remaining_quantity_base = int(lot.remaining_quantity_base) + int(credit_amount_base)
                sync_lot_quantities_from_base(lot, item)
                credit_amount = from_base_quantity(
                    base_amount=credit_amount_base,
                    unit_name=lot.unit,
                    ingredient_id=item.id,
                    density=item.density,
                )

                # Create audit record for this credit
                event_code = generate_inventory_event_code(change_type, item_id=item.id, code_type="event")

                history_record = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=credit_amount,
                    quantity_change_base=credit_amount_base,
                    unit=lot.unit,
                    unit_cost=lot.unit_cost,
                    notes=f"{change_type.title()}: Credited {credit_amount} back to lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                    created_by=created_by,
                    organization_id=item.organization_id,
                    affected_lot_id=lot.id,  # Link to the specific lot that was credited
                    batch_id=batch_id,
                    fifo_code=event_code
                )
                db.session.add(history_record)

                remaining_to_credit_base -= credit_amount_base
                lots_credited += 1

                logger.info(f"LOT_CREDITING: Credited {credit_amount} back to lot {lot.id} ({lot.fifo_code}), new remaining: {lot.remaining_quantity}")

        # If there's still quantity to credit after filling existing lots, create a new lot
        if remaining_to_credit_base > 0:
            remaining_to_credit = from_base_quantity(
                base_amount=remaining_to_credit_base,
                unit_name=unit,
                ingredient_id=item.id,
                density=item.density,
            )
            logger.info(f"LOT_CREDITING: Creating new lot for overflow {remaining_to_credit} {unit}")

            # Ensure quantity is not None before creating the overflow lot
            if remaining_to_credit is None:
                return False, f"Invalid quantity for overflow lot: {remaining_to_credit}", 0
            
            success, message, overflow_lot_id = create_new_fifo_lot(
                item_id=item.id,
                quantity=remaining_to_credit,
                quantity_base=remaining_to_credit_base,
                change_type=change_type,
                unit=unit,
                notes=f"{change_type.title()} overflow: {remaining_to_credit}" + (f" | {notes}" if notes else ""),
                cost_per_unit=final_cost,
                created_by=created_by,
                batch_id=batch_id
            )

            if not success:
                return False, f"Failed to create overflow lot: {message}", 0

        # Generate success message
        if lots_credited > 0 and remaining_to_credit_base > 0:
            success_msg = f"Credited to {lots_credited} existing lots and created overflow lot"
        elif lots_credited > 0:
            success_msg = f"Credited back to {lots_credited} existing lots using FIFO order"
        else:
            success_msg = f"Created new lot for {change_type}"

        logger.info(f"LOT_CREDITING SUCCESS: {success_msg}")
        return True, success_msg, float(quantity)

    except Exception as e:
        logger.error(f"Error in lot crediting operation {change_type}: {str(e)}")
        return False, f"Failed to credit inventory: {str(e)}", 0

# All additive operations now go through _universal_additive_handler

def get_additive_operation_info(change_type):
    """Get information about an additive operation"""
    group_name, group_config = _get_operation_group(change_type)
    if group_config:
        return {
            'group': group_name,
            'description': group_config['description'],
            'creates_lot': group_config['creates_lot'],
            'creates_history': group_config['creates_history']
        }
    return None