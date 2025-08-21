"""
Deductive Operations Handler

Handles all operations that REMOVE inventory using centralized registry configuration.
"""

import logging
from ._operation_registry import get_operation_config, is_deductive_operation
from ._fifo_ops import _handle_deductive_operation_internal

logger = logging.getLogger(__name__)


def handle_deductive_operation(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Universal handler for all deductive operations using centralized registry.
    """
    try:
        if not is_deductive_operation(change_type):
            return False, f"Not a deductive operation: {change_type}"

        config = get_operation_config(change_type)

        # Filter out parameters not accepted by FIFO deduction function
        fifo_kwargs = {k: v for k, v in kwargs.items() if k in ['batch_id']}

        # Handle deduction using FIFO
        success, error_msg = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes or config['message'],
            created_by=created_by,
            **fifo_kwargs
        )

        if not success:
            return False, error_msg

        # Return success message from registry
        return True, f"{config['message']} {quantity} {getattr(item, 'unit', 'units')}"

    except Exception as e:
        logger.error(f"Error in deductive operation {change_type}: {str(e)}")
        return False, f"Error processing {change_type}: {str(e)}"