"""
Core Inventory Adjustment Service

This is the CANONICAL entry point for all inventory changes.
All inventory adjustments MUST go through process_inventory_adjustment().
"""

import logging
import inspect
from sqlalchemy.exc import SQLAlchemyError
from app.models import db, InventoryItem, UnifiedInventoryHistory
from ._handlers import get_operation_handler
from ._validation import validate_operation_type

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
) -> tuple[bool, str]:
    """
    THE CANONICAL DISPATCHER for all inventory adjustments.
    Uses simplified handler system with centralized operation registry.
    """
    caller_info = inspect.stack()[1]
    caller_path = caller_info.filename.replace('/home/runner/workspace/', '')
    caller_function = caller_info.function.replace('call_with_inventory_operation', 'inventory_operation') # Added to fix the name of the calling function

    logger.info(f"CANONICAL DISPATCHER: item_id={item_id}, quantity={quantity}, change_type={change_type}, caller={caller_path}:{caller_function}")

    try:
        # Get the inventory item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            logger.error(f"Inventory item not found: {item_id}")
            return False, "Inventory item not found"

        # Check if this is initial stock (no existing history)
        is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0
        
        # CRITICAL FIX: We determine the handler type but DO NOT mutate change_type when calling handler
        handler_type = 'initial_stock' if is_initial_stock else change_type

        # Validate operation type using centralized registry
        if not validate_operation_type(handler_type): # Validate the determined handler type
            logger.error(f"Unknown inventory change type: '{handler_type}' (original: '{change_type}')")
            return False, f"Unknown inventory change type: '{change_type}'"

        # Get handler from simplified system
        handler = get_operation_handler(handler_type)
        if not handler:
            logger.error(f"No handler found for change type: '{handler_type}'")
            return False, f"No handler found for change type: '{change_type}'"

        # Dispatch the call
        try:
            # Pass the ORIGINAL change_type to the handler, not the mutated one
            success, message = handler(
                item=item,
                quantity=quantity,
                change_type=change_type,  # Original change_type preserved
                unit=unit,
                notes=notes,
                created_by=created_by,
                cost_override=cost_override,
                expiration_date=custom_expiration_date,
                shelf_life_days=custom_shelf_life_days,
                **kwargs
            )

            if success:
                db.session.commit()
                logger.info(f"Successfully processed {change_type} for item {item_id}")
                return True, message
            else:
                db.session.rollback()
                logger.warning(f"Handler failed for {change_type} on item {item_id}: {message}")
                return False, message

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error executing handler for {change_type} on item {item.id}: {e}", exc_info=True)
            return False, "A critical internal error occurred"

    except Exception as e:
        logger.error(f"Error in process_inventory_adjustment: {str(e)}")
        db.session.rollback()
        return False, str(e)