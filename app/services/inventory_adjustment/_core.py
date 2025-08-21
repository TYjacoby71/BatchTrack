
import inspect
import logging
from datetime import datetime
from app.models import db, InventoryItem, UnifiedInventoryHistory
from ._validation import validate_inventory_fifo_sync
from ._audit import record_audit_entry
from ._handlers import get_operation_handler

logger = logging.getLogger(__name__)


def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str = None,
    notes: str = None,
    created_by: int = None,
    cost_override: float = None,
    custom_expiration_date=None,
    custom_shelf_life_days: int = None,
    **kwargs
) -> tuple:
    """
    THE CANONICAL DISPATCHER for all inventory adjustments.
    
    Uses the Strategy Pattern to delegate work to specialist functions.
    Each change_type maps to exactly one specialist function.
    
    Returns: (success: bool, message: str)
    """
    caller_info = inspect.stack()[1]
    caller_path = caller_info.filename.replace('/home/runner/workspace/', '')
    caller_function = caller_info.function

    logger.info(f"CANONICAL DISPATCHER: item_id={item_id}, quantity={quantity}, change_type={change_type}, caller={caller_path}:{caller_function}")

    try:
        # Get the inventory item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            logger.error(f"Inventory item not found: {item_id}")
            return False, "Inventory item not found"

        # Check if this is initial stock (no existing history)
        is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0
        
        if is_initial_stock:
            logger.info(f"INITIAL STOCK: Detected item {item_id} has no FIFO history, using initial_stock handler")
            change_type = 'initial_stock'

        # ========== THE REGISTRY DISPATCHER LOGIC ==========
        
        # Get handler from the centralized registry
        handler = get_operation_handler(change_type)
        
        if not handler:
            logger.error(f"Unknown inventory change type: '{change_type}'")
            return False, f"Unknown inventory change type: '{change_type}'"
            
        # 4. Dispatch the call
        try:
            success, message = handler(
                item=item,
                quantity=quantity,
                notes=notes,
                created_by=created_by,
                cost_override=cost_override,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days,
                **kwargs
            )
            
            if success:
                db.session.commit()
                record_audit_entry(item_id, change_type, notes or f'{change_type}: {quantity}')
                return True, message
            else:
                db.session.rollback()
                return False, message
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error executing handler for {change_type} on item {item.id}: {e}")
            return False, "A critical internal error occurred"

    except Exception as e:
        logger.error(f"Error in process_inventory_adjustment: {str(e)}")
        db.session.rollback()
        return False, str(e)
