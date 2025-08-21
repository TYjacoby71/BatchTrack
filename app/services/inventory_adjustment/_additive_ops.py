"""
Additive Operations Handler

Handles all operations that ADD inventory (restock, manual_addition, etc.)
"""

import logging
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

# Configuration for additive operations
ADDITIVE_CONFIGS = {
    'restock': {'message': 'Restocked', 'use_cost_override': True},
    'manual_addition': {'message': 'Added manually', 'use_cost_override': False},
    'returned': {'message': 'Returned', 'use_cost_override': False},
    'refunded': {'message': 'Refunded', 'use_cost_override': False},
    'finished_batch': {'message': 'Added from finished batch', 'use_cost_override': False},
    'unreserved': {'message': 'Unreserved', 'use_cost_override': False},
}

def handle_additive_operation(item, quantity, change_type, notes=None, created_by=None, cost_override=None, **kwargs):
    """Universal handler for all additive operations"""
    try:
        if change_type not in ADDITIVE_CONFIGS:
            return False, f"Unknown additive operation: {change_type}"

        config = ADDITIVE_CONFIGS[change_type]

        # Determine cost per unit
        if config.get('use_cost_override') and cost_override is not None:
            cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit

        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            **kwargs
        )

        if success:
            message = f"{config['message']} {quantity} {getattr(item, 'unit', 'units')}"
            return True, message
        return False, error

    except Exception as e:
        logger.error(f"Error in additive operation {change_type}: {str(e)}")
        return False, str(e)


# Individual handler functions for each additive operation type
def handle_restock(item, quantity, notes=None, created_by=None, cost_override=None, expiration_date=None, shelf_life_days=None, **kwargs):
    """Handle restock operations - creates both FIFO entry and lot object"""
    from ._fifo_ops import _internal_add_fifo_entry_enhanced
    from ._lot_ops import create_inventory_lot

    try:
        # Create FIFO entry first
        success, message = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='restock',
            unit=item.unit or 'count',
            notes=notes or 'Restocked inventory',
            cost_per_unit=cost_override or item.cost_per_unit or 0.0,
            created_by=created_by,
            expiration_date=expiration_date,
            shelf_life_days=shelf_life_days,
            **kwargs
        )

        if not success:
            logger.error(f"RESTOCK: Failed to add FIFO entry: {message}")
            return False, message

        # Create corresponding lot object
        lot_success, lot_message, lot = create_inventory_lot(
            item_id=item.id,
            quantity=quantity,
            unit=item.unit or 'count',
            unit_cost=cost_override or item.cost_per_unit or 0.0,
            source_type='restock',
            source_notes=notes,
            created_by=created_by,
            expiration_date=expiration_date,
            shelf_life_days=shelf_life_days,
            **kwargs
        )

        if not lot_success:
            logger.warning(f"RESTOCK: FIFO entry created but lot creation failed: {lot_message}")
            # Continue anyway since FIFO entry was successful

        logger.info(f"RESTOCK: Successfully added {quantity} {item.unit or 'units'} to item {item.id}")
        return True, message

    except Exception as e:
        logger.error(f"Error in restock handler: {str(e)}")
        return False, str(e)

def handle_manual_addition(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle manual addition operations"""
    return handle_additive_operation(item, quantity, 'manual_addition', notes, created_by, **kwargs)

def handle_returned(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle returned inventory operations"""
    return handle_additive_operation(item, quantity, 'returned', notes, created_by, **kwargs)

def handle_refunded(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle refunded inventory operations"""
    return handle_additive_operation(item, quantity, 'refunded', notes, created_by, **kwargs)

def handle_finished_batch(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle finished batch operations"""
    return handle_additive_operation(item, quantity, 'finished_batch', notes, created_by, **kwargs)