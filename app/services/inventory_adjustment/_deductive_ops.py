"""
Deductive operations handler - operations that decrease inventory quantity.
Simplified to use single handler with operation-specific notes.
"""

import logging
from app.models import db
from ._fifo_ops import deduct_fifo_inventory

logger = logging.getLogger(__name__)

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

def _handle_deductive_operation(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Universal handler for all deductive operations.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"{change_type.upper()}: Deducting {quantity} from item {item.id}")

        # Enhance notes with operation-specific information
        enhanced_notes = notes or ""

        # Add operation-specific details
        if change_type == 'sale':
            if kwargs.get('customer'):
                enhanced_notes += f" (Customer: {kwargs['customer']})"
            if kwargs.get('sale_price'):
                enhanced_notes += f" (Sale Price: ${kwargs['sale_price']})"
            if kwargs.get('order_id'):
                enhanced_notes += f" (Order: {kwargs['order_id']})"

        # Use FIFO deduction logic
        success, message = deduct_fifo_inventory(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=enhanced_notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        # Return negative delta for core to apply
        quantity_delta = -float(quantity)

        # Get description from mapping or use generic one
        description = DEDUCTION_DESCRIPTIONS.get(change_type, f'Used {quantity} from inventory')
        success_message = description.format(quantity)

        logger.info(f"{change_type.upper()} SUCCESS: Will decrease item {item.id} by {abs(quantity_delta)}")
        return True, success_message, quantity_delta

    except Exception as e:
        logger.error(f"Error in {change_type} operation: {str(e)}")
        return False, f"{change_type.title()} operation failed: {str(e)}", 0

# Create individual handler functions that all use the universal handler
def handle_use(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_sale(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_spoil(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_trash(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_expired(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_damaged(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_quality_fail(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_sample(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_tester(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_gift(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_reserved(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)

def handle_batch(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    return _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs)