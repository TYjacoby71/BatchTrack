"""
Deductive operations handler - operations that decrease inventory quantity.
Unified to use single handler with operation type delegation.
"""

import logging
from app.models import db
from ._fifo_ops import deduct_fifo_inventory

logger = logging.getLogger(__name__)

# Deductive operation groups - all deductive operations follow the same pattern
DEDUCTIVE_OPERATION_GROUPS = {
    'consumption': {
        'operations': ['use', 'sale', 'sample', 'tester', 'gift', 'batch'],
        'description': 'Operations that consume inventory through normal usage',
        'creates_lot': False,
        'creates_history': True
    },
    'disposal': {
        'operations': ['spoil', 'trash', 'expired', 'damaged', 'quality_fail'],
        'description': 'Operations that remove inventory due to quality issues',
        'creates_lot': False,
        'creates_history': True
    },
    'reservation': {
        'operations': ['reserved'],
        'description': 'Operations that reserve inventory for future use',
        'creates_lot': False,
        'creates_history': True
    }
}

# Mapping of operation types to user-friendly descriptions
DEDUCTION_DESCRIPTIONS = {
    'use': 'Used {} from inventory',
    'sale': 'Sold {} from inventory',
    'spoil': 'Removed {} spoiled from inventory',
    'trash': 'Removed {} disposed from inventory',
    'expired': 'Removed {} expired from inventory',
    'damaged': 'Removed {} damaged from inventory',
    'quality_fail': 'Removed {} quality failed from inventory',
    'sample': 'Used {} for samples',
    'tester': 'Used {} for testers',
    'gift': 'Used {} for gifts',
    'reserved': 'Reserved {} from inventory',
    'batch': 'Used {} in batch production'
}

def _get_operation_group(change_type):
    """Determine which operation group a change_type belongs to"""
    for group_name, group_config in DEDUCTIVE_OPERATION_GROUPS.items():
        if change_type in group_config['operations']:
            return group_name, group_config
    return None, None

def _handle_deductive_operation(item, quantity, quantity_base, change_type, notes, created_by, customer=None, sale_price=None, order_id=None, batch_id=None):
    """
    Universal handler for all deductive operations.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"DEDUCTIVE: Processing {change_type} for item {item.id}, quantity={quantity}")

        # Get operation group info
        group_name, group_config = _get_operation_group(change_type)
        if not group_config:
            logger.error(f"DEDUCTIVE: Unknown change type '{change_type}'")
            return False, f"Unknown deductive operation: '{change_type}'", 0

        logger.info(f"DEDUCTIVE: {change_type} -> {group_name} group")

        # Enhance notes with operation-specific information
        enhanced_notes = notes or ""

        # Add operation-specific details for sales
        if change_type == 'sale':
            if customer:
                enhanced_notes += f" (Customer: {customer})"
            if sale_price is not None:
                enhanced_notes += f" (Sale Price: ${sale_price})"
            if order_id:
                enhanced_notes += f" (Order: {order_id})"

        # Normalize sign: callers may pass negative numbers for deductions; use absolute for processing
        qty_abs = abs(float(quantity))
        qty_abs_base = abs(int(quantity_base))

        # Use FIFO deduction logic (valuation handled inside based on org/batch method)
        success, message = deduct_fifo_inventory(
            item_id=item.id,
            quantity_to_deduct=qty_abs,
            quantity_to_deduct_base=qty_abs_base,
            change_type=change_type,
            notes=enhanced_notes,
            created_by=created_by,
            batch_id=batch_id
        )

        if not success:
            logger.error(f"DEDUCTIVE: FIFO deduction failed for {change_type}: {message}")
            return False, message, 0

        # Return the actual quantity delta (negative for deductions)
        quantity_delta = -qty_abs
        quantity_delta_base = -qty_abs_base

        # Get description from mapping or use generic one
        description = DEDUCTION_DESCRIPTIONS.get(change_type, f'Used {quantity} from inventory')
        success_message = description.format(quantity)

        logger.info(f"DEDUCTIVE SUCCESS: {change_type} will decrease item {item.id} by {abs(quantity_delta)}")
        return True, success_message, quantity_delta, quantity_delta_base

    except Exception as e:
        logger.error(f"DEDUCTIVE ERROR: {change_type} operation failed: {str(e)}")
        return False, f"{change_type.title()} operation failed: {str(e)}", 0

def get_deductive_operation_info(change_type):
    """Get information about a deductive operation"""
    group_name, group_config = _get_operation_group(change_type)
    if group_config:
        return {
            'group': group_name,
            'description': group_config['description'],
            'creates_lot': group_config['creates_lot'],
            'creates_history': group_config['creates_history']
        }
    return None