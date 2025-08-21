
"""
Deductive Operations Handler

Handles all operations that REMOVE inventory (use, sale, spoil, etc.)
"""

import logging
from ._fifo_ops import _handle_deductive_operation_internal

logger = logging.getLogger(__name__)

# Configuration for deductive operations
DEDUCTIVE_CONFIGS = {
    'use': {'message': 'Used'},
    'batch': {'message': 'Used in batch'},
    'sale': {'message': 'Sold'},
    'spoil': {'message': 'Marked as spoiled'},
    'trash': {'message': 'Trashed'},
    'expired': {'message': 'Removed (expired)'},
    'damaged': {'message': 'Removed (damaged)'},
    'quality_fail': {'message': 'Removed (quality fail)'},
    'sample': {'message': 'Used for sample'},
    'tester': {'message': 'Used for tester'},
    'gift': {'message': 'Gave as gift'},
    'reserved': {'message': 'Reserved'},
    'recount_deduction': {'message': 'Recount adjustment'}
}

def handle_deductive_operation(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """Universal handler for all deductive operations"""
    try:
        if change_type not in DEDUCTIVE_CONFIGS:
            return False, f"Unknown deductive operation: {change_type}"
        
        config = DEDUCTIVE_CONFIGS[change_type]
        
        success = _handle_deductive_operation_internal(
            item, quantity, change_type, notes, created_by, **kwargs
        )
        
        if success:
            message = f"{config['message']} {quantity} {getattr(item, 'unit', 'units')}"
            return True, message
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in deductive operation {change_type}: {str(e)}")
        return False, str(e)
