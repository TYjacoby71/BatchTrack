
"""
Handler registry for inventory adjustment operations.
Provides a centralized mapping of change_types to their respective handler functions.
"""

def get_operation_handler(change_type: str):
    """
    Get the appropriate handler function for a given change_type.
    
    This registry maps change types to their specialist handler functions.
    Each handler must accept (item, quantity, notes, created_by, **kwargs).
    
    Returns the handler function or None if not found.
    """
    
    # Import handlers locally to avoid circular imports
    from ._additive_ops import handle_additive_operation
    from ._deductive_ops import handle_deductive_operation
    from ._special_ops import handle_special_operation
    from ._creation_logic import handle_initial_stock
    from ._recount_logic import handle_recount_adjustment_clean
    
    # Registry mapping change_types to their handlers
    OPERATION_HANDLERS = {
        # Additive operations (add inventory)
        'restock': handle_additive_operation,
        'found': handle_additive_operation,
        'return': handle_additive_operation,
        'adjustment_increase': handle_additive_operation,
        'production_yield': handle_additive_operation,
        'recount_increase': handle_additive_operation,
        
        # Deductive operations (remove inventory) 
        'use': handle_deductive_operation,
        'waste': handle_deductive_operation,
        'expired': handle_deductive_operation,
        'lost': handle_deductive_operation,
        'sold': handle_deductive_operation,
        'damaged': handle_deductive_operation,
        'adjustment_decrease': handle_deductive_operation,
        'sample': handle_deductive_operation,
        'recount_deduction': handle_deductive_operation,
        
        # Special operations (non-quantity changes)
        'cost_override': handle_special_operation,
        'unit_conversion': handle_special_operation,
        
        # Initial stock creation
        'initial_stock': handle_initial_stock,
        
        # Recount operations
        'recount': handle_recount_adjustment_clean,
    }
    
    return OPERATION_HANDLERS.get(change_type)
