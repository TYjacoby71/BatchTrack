"""
DEPRECATED: This handlers registry is no longer used.

Core now delegates directly to operation modules:
- _additive_ops.py for additive operations  
- _deductive_ops.py for deductive operations
- _special_ops.py and _recount_logic.py for special operations

This file is kept temporarily for any remaining references but should be removed.
"""

# Legacy compatibility - these should not be used anymore
OPERATION_HANDLERS = {}
ADDITIVE_OPS = {}
DEDUCTIVE_OPS = {}
SPECIAL_OPS = {}

def get_operation_handler(change_type):
    """
    DEPRECATED: Core now delegates directly to operation modules.
    This function should not be used anymore.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"DEPRECATED: get_operation_handler() called for {change_type}. Core now delegates directly.")
    return None

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