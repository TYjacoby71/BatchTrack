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
    """
    Universal handler for all additive operations.

    Standardized pattern:
    1. Validate operation type
    2. Determine cost per unit based on config
    3. Add FIFO entry
    4. Return standardized message
    """
    try:
        if change_type not in ADDITIVE_CONFIGS:
            return False, f"Unknown additive operation: {change_type}"

        config = ADDITIVE_CONFIGS[change_type]

        # Standardized cost determination
        if config.get('use_cost_override') and cost_override is not None:
            cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit or 0.0

        # Standard FIFO entry creation
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=item.unit or 'count',
            notes=notes or f"{config['message']} inventory",
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            **kwargs
        )

        if success:
            message = f"{config['message']} {quantity} {item.unit or 'units'}"
            logger.info(f"ADDITIVE: {message} for item {item.id}")
            return True, message
        else:
            logger.error(f"ADDITIVE: Failed {change_type} for item {item.id}: {error}")
            return False, error

    except Exception as e:
        logger.error(f"ADDITIVE: Error in {change_type} for item {item.id}: {str(e)}")
        return False, str(e)


# Individual handler functions for each additive operation type
def handle_restock(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
    """Handle restock operations"""
    return handle_additive_operation(item, quantity, 'restock', notes, created_by, cost_override, **kwargs)

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