"""
Handler registry for inventory adjustment operations.
Provides a centralized mapping of change_types to their respective handler functions.
"""

# Import handlers locally to avoid circular imports
from ._additive_ops import handle_restock, handle_manual_addition, handle_returned, handle_refunded, handle_finished_batch
from ._deductive_ops import handle_use, handle_sale, handle_spoil, handle_expired, handle_damaged, handle_quality_fail, handle_sample, handle_tester, handle_gift, handle_reserved, handle_batch
from ._recount_logic import handle_recount
from ._special_ops import handle_cost_override, handle_unit_conversion
from ._creation_logic import handle_initial_stock


# Registry mapping change_types to their handlers
OPERATION_HANDLERS = {
    # Additive operations (create new FIFO lots)
    'restock': handle_restock,
    'manual_addition': handle_manual_addition,
    'returned': handle_returned,
    'refunded': handle_refunded,
    'finished_batch': handle_finished_batch,
    'initial_stock': handle_initial_stock,

    # Deductive operations (consume from FIFO lots)
    'use': handle_use,
    'sale': handle_sale,
    'spoil': handle_spoil,
    'trash': handle_spoil,  # Alias for spoil
    'expired': handle_expired,
    'damaged': handle_damaged,
    'quality_fail': handle_quality_fail,
    'sample': handle_sample,
    'tester': handle_tester,
    'gift': handle_gift,
    'reserved': handle_reserved,
    'batch': handle_batch,

    # Special operations (non-FIFO operations)
    'recount': handle_recount,
    'cost_override': handle_cost_override,
    'unit_conversion': handle_unit_conversion,
}


def get_operation_handler(change_type: str):
    """
    Get the appropriate handler function for a given change_type.

    This registry maps change types to their specialist handler functions.
    Each handler must accept (item, quantity, notes, created_by, **kwargs).

    Returns the handler function or None if not found.
    """
    return OPERATION_HANDLERS.get(change_type)


def get_all_operation_types():
    """Get all supported operation types"""
    return list(OPERATION_HANDLERS.keys())


def is_additive_operation(change_type: str) -> bool:
    """Check if operation adds inventory"""
    additive_ops = {'restock', 'manual_addition', 'returned', 'refunded', 'finished_batch', 'initial_stock'}
    return change_type in additive_ops


def is_deductive_operation(change_type: str) -> bool:
    """Check if operation removes inventory"""
    deductive_ops = {'use', 'sale', 'spoil', 'trash', 'expired', 'damaged', 'quality_fail', 'sample', 'tester', 'gift', 'reserved', 'batch'}
    return change_type in deductive_ops


def is_special_operation(change_type: str) -> bool:
    """Check if operation is a special non-FIFO operation"""
    special_ops = {'recount', 'cost_override', 'unit_conversion'}
    return change_type in special_ops