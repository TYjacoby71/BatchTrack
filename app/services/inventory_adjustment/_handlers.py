"""
Handler registry for inventory adjustment operations.
Provides a centralized mapping of change_types to their respective handler functions.
"""

# Import handlers locally to avoid circular imports
from ._additive_ops import _universal_additive_handler
from ._deductive_ops import handle_use, handle_sale, handle_spoil, handle_trash, handle_expired, handle_damaged, handle_quality_fail, handle_sample, handle_tester, handle_gift, handle_reserved, handle_batch
from ._recount_logic import handle_recount
from ._special_ops import handle_cost_override, handle_unit_conversion
from ._creation_logic import handle_initial_stock


"""Grouped handler registry for clarity and future routing by family."""

ADDITIVE_OPS = {
    'restock': _universal_additive_handler,
    'manual_addition': _universal_additive_handler,
    'returned': _universal_additive_handler,
    'refunded': _universal_additive_handler,
    'finished_batch': _universal_additive_handler,
    'release_reservation': _universal_additive_handler,
    'initial_stock': handle_initial_stock,
}

DEDUCTIVE_OPS = {
    'use': handle_use,
    'sale': handle_sale,
    'spoil': handle_spoil,
    'trash': handle_trash,
    'expired': handle_expired,
    'damaged': handle_damaged,
    'quality_fail': handle_quality_fail,
    'sample': handle_sample,
    'tester': handle_tester,
    'gift': handle_gift,
    'reserved': handle_reserved,
    'batch': handle_batch,
}

SPECIAL_OPS = {
    'recount': handle_recount,
    'cost_override': handle_cost_override,
    'unit_conversion': handle_unit_conversion,
}

OPERATION_HANDLERS = {
    **ADDITIVE_OPS,
    **DEDUCTIVE_OPS,
    **SPECIAL_OPS,
}


def get_operation_handler(change_type: str):
    """
    Get the appropriate handler function for a given change_type.

    This registry maps change types to their specialist handler functions.
    Each handler must accept explicit parameters: (item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, customer, sale_price, order_id, target_quantity).

    Returns the handler function or None if not found.
    """
    return OPERATION_HANDLERS.get(change_type)


def get_all_operation_types():
    """Get all supported operation types"""
    return list(OPERATION_HANDLERS.keys())


def is_additive_operation(change_type: str) -> bool:
    """Check if operation adds inventory"""
    return change_type in ADDITIVE_OPS


def is_deductive_operation(change_type: str) -> bool:
    """Check if operation removes inventory"""
    return change_type in DEDUCTIVE_OPS


def is_special_operation(change_type: str) -> bool:
    """Check if operation is a special non-FIFO operation"""
    return change_type in SPECIAL_OPS