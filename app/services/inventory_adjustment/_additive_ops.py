
"""
Additive operations handler - operations that increase inventory quantity.
These handlers calculate what needs to happen and return deltas.
They should NEVER directly modify item.quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory
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

def _universal_additive_handler(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
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
        unit = kwargs.get('unit') or item.unit or 'count'

        # Use provided cost or item's default cost
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        quantity_delta = float(quantity)

        if group_name == 'lot_creation':
            # Operations that create new lots (restock, manual_addition, finished_batch)
            success, message, lot_id = _handle_lot_creation_operation(
                item, quantity, change_type, unit, notes, final_cost, 
                created_by, custom_expiration_date, custom_shelf_life_days, **kwargs
            )
            
        elif group_name == 'lot_crediting':
            # Operations that credit back to existing lots (returned, refunded, release_reservation)
            success, message, lot_id = _handle_lot_crediting_operation(
                item, quantity, change_type, unit, notes, final_cost, 
                created_by, **kwargs
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
        return True, success_message, quantity_delta

    except Exception as e:
        logger.error(f"Error in {change_type} operation: {str(e)}")
        return False, f"{change_type.replace('_', ' ').title()} failed: {str(e)}", 0



def _handle_lot_creation_operation(item, quantity, change_type, unit, notes, final_cost, created_by, custom_expiration_date, custom_shelf_life_days, **kwargs):
    """Handle operations that create new lots"""
    logger.info(f"LOT_CREATION: Creating new lot for {change_type}")
    
    # Remove unit from kwargs if it exists to avoid conflict
    kwargs.pop('unit', None)
    
    # Create FIFO entry (lot) with proper source tracking
    success, message, lot_id = create_new_fifo_lot(
        item_id=item.id,
        quantity=quantity,
        change_type=change_type,
        unit=unit,
        notes=notes,
        cost_per_unit=final_cost,
        created_by=created_by,
        custom_expiration_date=custom_expiration_date,
        custom_shelf_life_days=custom_shelf_life_days,
        **kwargs
    )

    if not success:
        return False, f"Failed to create lot: {message}", None

    # Note: create_new_fifo_lot already creates the history record
    # No additional history record needed for lot creation operations
    
    logger.info(f"LOT_CREATION: Successfully created lot {lot_id} for {change_type}")
    return True, message, lot_id

def _handle_lot_crediting_operation(item, quantity, change_type, unit, notes, final_cost, created_by, **kwargs):
    """Handle operations that credit back to existing FIFO lots"""
    from ._fifo_ops import process_fifo_deduction
    
    logger.info(f"LOT_CREDITING: Processing {change_type} credit operation")
    
    # For crediting operations, we need to add inventory back using FIFO logic
    # This will credit the oldest lots first (reverse FIFO for returns)
    try:
        # For now, treat crediting operations as lot creation
        # TODO: Implement proper FIFO crediting logic that finds and credits existing lots
        success, message, lot_id = create_new_fifo_lot(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by
        )

        if not success:
            return False, f"Failed to credit inventory: {message}", None

        logger.info(f"LOT_CREDITING: Successfully credited {quantity} {unit} for {change_type}")
        return True, message, lot_id

    except Exception as e:
        logger.error(f"Error in lot crediting operation {change_type}: {str(e)}")
        return False, f"Failed to credit inventory: {str(e)}", None

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
