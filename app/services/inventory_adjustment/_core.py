
import logging
from app.models import db, InventoryItem, UnifiedInventoryHistory
from ._handlers import get_operation_handler
from ._validation import validate_inventory_fifo_sync

logger = logging.getLogger(__name__)

def process_inventory_adjustment(item_id, change_type, quantity, **kwargs):
    """
    Canonical entry point for all inventory adjustments.
    This is the ONLY function that should be called by external code.
    """
    logger.info(f"CANONICAL: item_id={item_id}, qty={quantity}, type={change_type}")
    
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, "Inventory item not found."

    # Check if this is the first entry for this item
    is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0
    
    # CRITICAL FIX: We check for initial stock but DO NOT mutate the change_type
    # We route to initial_stock handler ONLY if it's the first entry, otherwise use original change_type
    handler_type = 'initial_stock' if is_initial_stock else change_type
    
    handler = get_operation_handler(handler_type)
    
    if not handler:
        return False, f"Unknown inventory change type: '{change_type}'"
    
    try:
        # Pass the ORIGINAL change_type to the handler, not the mutated one
        success, message = handler(
            item=item, 
            quantity=quantity, 
            change_type=change_type,  # Original intent preserved
            **kwargs
        )
        
        if success:
            db.session.commit()
            logger.info(f"SUCCESS: {change_type} operation completed for item {item.id}")
            return True, message
        else:
            db.session.rollback()
            logger.error(f"FAILED: {change_type} operation failed for item {item.id}: {message}")
            return False, message
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Handler error for {change_type} on item {item.id}: {e}", exc_info=True)
        return False, "A critical internal error occurred."

# Backwards compatibility shims
def InventoryAdjustmentService():
    """Legacy compatibility shim"""
    class Shim:
        @staticmethod
        def process_inventory_adjustment(*args, **kwargs):
            return process_inventory_adjustment(*args, **kwargs)
        
        @staticmethod
        def validate_inventory_fifo_sync(*args, **kwargs):
            return validate_inventory_fifo_sync(*args, **kwargs)
    
    return Shim()
