
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
