
"""
Operation Handlers Registry

This module contains the mapping from change_types to their handler functions.
Each handler is focused on a specific type of inventory operation.
"""

from ._additive_ops import handle_additive_operation
from ._deductive_ops import handle_deductive_operation  
from ._special_ops import handle_cost_override_special
from ._recount_logic import handle_recount_adjustment_clean
from ._creation_logic import handle_initial_stock

# The master operation registry - this is your "dictionary approach"
OPERATION_HANDLERS = {
    # Additive operations
    'restock': handle_additive_operation,
    'manual_addition': handle_additive_operation,
    'returned': handle_additive_operation,
    'refunded': handle_additive_operation,
    'finished_batch': handle_additive_operation,
    'unreserved': handle_additive_operation,
    'initial_stock': handle_initial_stock,  # Special case
    
    # Deductive operations  
    'use': handle_deductive_operation,
    'batch': handle_deductive_operation,
    'sale': handle_deductive_operation,
    'spoil': handle_deductive_operation,
    'trash': handle_deductive_operation,
    'expired': handle_deductive_operation,
    'damaged': handle_deductive_operation,
    'quality_fail': handle_deductive_operation,
    'sample': handle_deductive_operation,
    'tester': handle_deductive_operation,
    'gift': handle_deductive_operation,
    'reserved': handle_deductive_operation,
    'recount_deduction': handle_deductive_operation,
    
    # Special operations
    'cost_override': handle_cost_override_special,
    'recount': handle_recount_adjustment_clean,
}

def get_operation_handler(change_type):
    """Get the appropriate handler for a change_type"""
    return OPERATION_HANDLERS.get(change_type)
