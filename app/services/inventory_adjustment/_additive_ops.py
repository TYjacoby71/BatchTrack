"""
Additive Operations Handler

Handles all operations that ADD inventory using centralized registry configuration.
"""

import logging
from ._operation_registry import get_operation_config, is_additive_operation
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)


def handle_additive_operation(item, quantity, change_type, notes=None, created_by=None, cost_override=None, **kwargs):
    """
    Universal handler for all additive operations using centralized registry.
    """
    try:
        if not is_additive_operation(change_type):
            return False, f"Not an additive operation: {change_type}"

        config = get_operation_config(change_type)

        # Determine cost per unit based on registry config
        if config.get('use_cost_override', False) and cost_override is not None:
            cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit or 0.0

        # Create FIFO entry
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
            # Update the main item quantity
            from app.models import db
            item.quantity = float(item.quantity or 0) + float(quantity)
            db.session.add(item)
            message = f"{config['message']} {quantity} {item.unit or 'units'}"
            logger.info(f"ADDITIVE: {message} for item {item.id}, new total: {item.quantity}")
            return True, message
        else:
            logger.error(f"ADDITIVE: Failed {change_type} for item {item.id}: {error}")
            return False, error

    except Exception as e:
        logger.error(f"ADDITIVE: Error in {change_type} for item {item.id}: {str(e)}")
        return False, str(e)