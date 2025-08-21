
import logging
from app.models import db, InventoryItem, UnifiedInventoryHistory
from ._handlers import get_operation_handler
from ._validation import validate_inventory_fifo_sync

logger = logging.getLogger(__name__)

def process_inventory_adjustment(item_id, change_type, quantity, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None):
    """
    Canonical entry point for all inventory adjustments.
    This is the ONLY function that should modify item.quantity.
    All handlers return deltas and let this core function apply the final quantity change.
    """
    logger.info(f"CANONICAL: item_id={item_id}, qty={quantity}, type={change_type}")

    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, "Inventory item not found."

    # Store original quantity for logging
    original_quantity = float(item.quantity)

    # Check if this is the first entry for this item
    is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0

    # Route to initial_stock handler ONLY if it's the first entry, otherwise use original change_type
    handler_type = 'initial_stock' if is_initial_stock else change_type

    handler = get_operation_handler(handler_type)
    if not handler:
        return False, f"Unknown inventory change type: '{change_type}'"

    try:
        # Call the handler - it should NOT modify item.quantity directly
        # Handlers should return (success, message, quantity_delta)
        result = handler(
            item=item,
            quantity=quantity,
            change_type=change_type,  # Original intent preserved
            notes=notes,
            created_by=created_by,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            customer=customer,
            sale_price=sale_price,
            order_id=order_id,
            target_quantity=target_quantity,
            unit=unit
        )

        # Handle different return formats for backwards compatibility
        if len(result) == 2:
            # Old format: (success, message)
            success, message = result
            quantity_delta = None
        elif len(result) == 3:
            # New format: (success, message, quantity_delta)
            success, message, quantity_delta = result
        else:
            logger.error(f"Handler returned unexpected format: {result}")
            return False, "Handler returned invalid response format"

        if not success:
            db.session.rollback()
            logger.error(f"FAILED: {change_type} operation failed for item {item.id}: {message}")
            return False, message

        # CRITICAL: Only this core function modifies item.quantity
        if quantity_delta is not None:
            new_quantity = float(item.quantity) + float(quantity_delta)
            logger.info(f"QUANTITY UPDATE: Item {item.id} quantity {item.quantity} + {quantity_delta} = {new_quantity}")
            item.quantity = new_quantity
        elif change_type == 'recount' and target_quantity is not None:
            # Special case for recount - set absolute quantity
            logger.info(f"RECOUNT: Item {item.id} quantity {item.quantity} -> {target_quantity}")
            item.quantity = float(target_quantity)

        db.session.commit()
        
        final_quantity = float(item.quantity)
        logger.info(f"SUCCESS: {change_type} operation completed for item {item.id}. Quantity: {original_quantity} -> {final_quantity}")
        return True, message

    except Exception as e:
        db.session.rollback()
        logger.error(f"Handler error for {change_type} on item {item.id}: {e}", exc_info=True)
        return False, "A critical internal error occurred."

# Backwards compatibility shims
def InventoryAdjustmentService():
    """Legacy compatibility shim"""
    class Shim:
        @staticmethod
        def process_inventory_adjustment(item_id, change_type, quantity, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None):
            return process_inventory_adjustment(item_id, change_type, quantity, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, customer, sale_price, order_id, target_quantity, unit)

        @staticmethod
        def validate_inventory_fifo_sync(item_id, expected_quantity=None):
            return validate_inventory_fifo_sync(item_id, expected_quantity)

    return Shim()
