"""
Operation Handlers - Simplified Dispatcher

Uses the centralized operation registry to route operations to their appropriate handlers.
"""

from ._operation_registry import (
    get_operation_config,
    get_operation_type,
    is_additive_operation,
    is_deductive_operation,
    is_special_operation,
    validate_operation_type,
    get_all_operation_types
)
from ._additive_ops import handle_additive_operation
from ._deductive_ops import handle_deductive_operation
from ._special_ops import handle_special_operation

import logging

logger = logging.getLogger(__name__)


def get_operation_handler(change_type: str):
    """
    Get the appropriate handler function for a change_type.
    Routes to additive, deductive, or special handlers based on operation registry.
    """
    if not validate_operation_type(change_type):
        logger.error(f"Unknown operation type: {change_type}")
        return None

    operation_type = get_operation_type(change_type)

    if operation_type == 'additive':
        return handle_additive_operation
    elif operation_type == 'deductive':
        return handle_deductive_operation
    elif operation_type == 'special':
        return handle_special_operation
    else:
        logger.error(f"Invalid operation type: {operation_type}")
        return None