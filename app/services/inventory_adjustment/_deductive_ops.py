
"""
Deductive operations handler - operations that decrease inventory quantity.
These handlers calculate what needs to happen and return deltas.
They should NEVER directly modify item.quantity.
"""

import logging
from app.models import db
from ._fifo_ops import _handle_deductive_operation_internal

logger = logging.getLogger(__name__)

def handle_use(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle inventory use - general consumption.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"USE: Deducting {quantity} from item {item.id}")
        
        # Use FIFO deduction logic
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        # Return negative delta for core to apply
        quantity_delta = -float(quantity)
        logger.info(f"USE SUCCESS: Will decrease item {item.id} by {abs(quantity_delta)}")
        return True, f"Used {quantity} from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in use operation: {str(e)}")
        return False, f"Use operation failed: {str(e)}", 0

def handle_sale(item, quantity, change_type, notes=None, created_by=None, customer=None, sale_price=None, order_id=None, **kwargs):
    """
    Handle inventory sale - items sold to customers.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"SALE: Deducting {quantity} from item {item.id}")
        
        # Enhance notes with sale information
        sale_notes = notes or ""
        if customer:
            sale_notes += f" (Customer: {customer})"
        if sale_price:
            sale_notes += f" (Sale Price: ${sale_price})"
        if order_id:
            sale_notes += f" (Order: {order_id})"

        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=sale_notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Sold {quantity} from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in sale operation: {str(e)}")
        return False, f"Sale operation failed: {str(e)}", 0

def handle_spoil(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle inventory spoilage - items that went bad.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"SPOIL: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Removed {quantity} spoiled from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in spoil operation: {str(e)}")
        return False, f"Spoil operation failed: {str(e)}", 0

def handle_trash(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle inventory disposal - items thrown away.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"TRASH: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Removed {quantity} disposed from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in trash operation: {str(e)}")
        return False, f"Trash operation failed: {str(e)}", 0

def handle_expired(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle expired inventory - items past expiration date.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"EXPIRED: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Removed {quantity} expired from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in expired operation: {str(e)}")
        return False, f"Expired operation failed: {str(e)}", 0

def handle_damaged(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle damaged inventory - items that are damaged.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"DAMAGED: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Removed {quantity} damaged from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in damaged operation: {str(e)}")
        return False, f"Damaged operation failed: {str(e)}", 0

def handle_quality_fail(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle quality control failures.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"QUALITY_FAIL: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Removed {quantity} quality failed from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in quality fail operation: {str(e)}")
        return False, f"Quality fail operation failed: {str(e)}", 0

def handle_sample(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle sampling - items used for testing/samples.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"SAMPLE: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Used {quantity} for samples", quantity_delta

    except Exception as e:
        logger.error(f"Error in sample operation: {str(e)}")
        return False, f"Sample operation failed: {str(e)}", 0

def handle_tester(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle tester items - items given as testers.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"TESTER: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Used {quantity} for testers", quantity_delta

    except Exception as e:
        logger.error(f"Error in tester operation: {str(e)}")
        return False, f"Tester operation failed: {str(e)}", 0

def handle_gift(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle gift items - items given as gifts.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"GIFT: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Used {quantity} for gifts", quantity_delta

    except Exception as e:
        logger.error(f"Error in gift operation: {str(e)}")
        return False, f"Gift operation failed: {str(e)}", 0

def handle_reserved(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle reservations - items set aside for specific use.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"RESERVED: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Reserved {quantity} from inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in reserved operation: {str(e)}")
        return False, f"Reserved operation failed: {str(e)}", 0

def handle_batch(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """
    Handle batch usage - items used in batch production.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"BATCH: Deducting {quantity} from item {item.id}")
        
        success, message = _handle_deductive_operation_internal(
            item_id=item.id,
            quantity_to_deduct=quantity,
            change_type=change_type,
            notes=notes,
            created_by=created_by
        )

        if not success:
            return False, message, 0

        quantity_delta = -float(quantity)
        return True, f"Used {quantity} in batch production", quantity_delta

    except Exception as e:
        logger.error(f"Error in batch operation: {str(e)}")
        return False, f"Batch operation failed: {str(e)}", 0
