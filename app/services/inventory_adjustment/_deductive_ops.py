
"""
Deductive Operations Handler

Handles all operations that REMOVE inventory (use, sale, spoil, etc.)
"""

import logging
from ._fifo_ops import _handle_deductive_operation_internal

logger = logging.getLogger(__name__)

# Configuration for deductive operations
DEDUCTIVE_CONFIGS = {
    'use': {'message': 'Used'},
    'batch': {'message': 'Used in batch'},
    'sale': {'message': 'Sold'},
    'spoil': {'message': 'Marked as spoiled'},
    'trash': {'message': 'Trashed (recorded as spoiled)'},  # Records as spoil
    'expired': {'message': 'Removed (expired)'},
    'damaged': {'message': 'Removed (damaged)'},
    'quality_fail': {'message': 'Removed (quality fail)'},
    'sample': {'message': 'Used for sample'},
    'tester': {'message': 'Used for tester'},
    'gift': {'message': 'Gave as gift'},
    'reserved': {'message': 'Reserved'},
    'recount_deduction': {'message': 'Recount adjustment'}
}

def handle_deductive_operation(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """
    Common handler for all deductive operations that remove inventory using FIFO.

    This includes: use, sale, spoil, expired, damaged, quality_fail, sample, tester, gift, reserved, batch
    """
    try:
        # Handle deduction using FIFO - this will check inventory internally
        success, error_msg = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by,
            customer=customer,
            sale_price=sale_price,
            order_id=order_id
        )

        if not success:
            return False, error_msg

        # Get success message from config
        config = DEDUCTIVE_CONFIGS.get(change_type, {})
        message = config.get('message', f'Deducted {quantity} {getattr(item, "unit", "units")}')

        return True, message.format(quantity=quantity, unit=getattr(item, 'unit', 'count'))

    except Exception as e:
        logger.error(f"Error in deductive operation {change_type}: {str(e)}")
        return False, f"Error processing {change_type}: {str(e)}"


# Individual handler functions for each deductive operation type
def handle_use(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle use operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_sale(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle sale operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_spoil(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle spoil operations - uses FIFO deduction and consumes from lots"""
    return handle_deductive_operation(item, quantity, change_type, notes or 'Spoiled inventory', created_by, customer, sale_price, order_id)

def handle_trash(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle trash operations - records as spoil but with different notes"""
    return handle_deductive_operation(item, quantity, 'spoil', notes or 'Trashed inventory', created_by, customer, sale_price, order_id)

def handle_expired(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle expired operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_damaged(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle damaged operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_quality_fail(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle quality fail operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_sample(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle sample operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_tester(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle tester operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_gift(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle gift operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_reserved(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle reserved operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)

def handle_batch(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None):
    """Handle batch operations"""
    return handle_deductive_operation(item, quantity, change_type, notes, created_by, customer, sale_price, order_id)
