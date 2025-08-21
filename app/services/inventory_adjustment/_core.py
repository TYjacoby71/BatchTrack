
import inspect
import logging
from datetime import datetime
from app.models import db, InventoryItem, UnifiedInventoryHistory
from ._validation import validate_inventory_fifo_sync
from ._audit import record_audit_entry
from ._recount_logic import handle_recount_adjustment

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
) -> bool:
    """
    Canonical entry point for ALL inventory adjustments.
    Delegates to FIFO service for lot management and deduction planning.
    """
    caller_info = inspect.stack()[1]
    caller_path = caller_info.filename.replace('/home/runner/workspace/', '')
    caller_function = caller_info.function

    logger.info(f"CANONICAL INVENTORY ADJUSTMENT: item_id={item_id}, quantity={quantity}, change_type={change_type}, caller={caller_path}:{caller_function}")

    try:
        # Get the inventory item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            logger.error(f"Inventory item not found: {item_id}")
            return False, "Inventory item not found"

        # Check if this is initial stock (no existing history)
        is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0
        
        if is_initial_stock:
            logger.info(f"INITIAL STOCK: Detected item {item_id} has no FIFO history, delegating to creation logic")
            from ._creation_logic import handle_initial_stock
            return handle_initial_stock(item, quantity, change_type, unit, notes, created_by, 
                                      cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)

        # Handle recount with special logic that uses FIFO service
        if change_type == 'recount':
            logger.info(f"RECOUNT: Processing recount from {item.quantity} to {quantity}")
            return handle_recount_adjustment(
                item_id=item_id,
                target_quantity=quantity,
                notes=notes,
                created_by=created_by,
                item_type=getattr(item, 'type', 'ingredient')
            )

        # Handle cost override (no quantity change)
        elif change_type == 'cost_override':
            if cost_override is not None:
                item.cost_per_unit = cost_override
                db.session.commit()
                record_audit_entry(item_id, 'cost_override', notes or f'Cost updated to {cost_override}')
                return True
            return False

        # Handle additive changes (restock, manual_addition, etc.)
        elif change_type in ['restock', 'manual_addition', 'returned', 'refunded', 'finished_batch']:
            return _handle_additive_adjustment(
                item_id, quantity, change_type, unit, notes, created_by, 
                cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs
            )

        # Handle deductive changes (spoil, trash, use, batch, recount, etc.)
        elif change_type in ['spoil', 'trash', 'expired', 'gift', 'sample', 'tester',
                           'quality_fail', 'damaged', 'sold', 'sale', 'use', 'batch',
                           'reserved', 'unreserved', 'recount']:
            return _handle_deductive_adjustment(
                item_id, quantity, change_type, unit, notes, created_by, **kwargs
            )

        else:
            logger.error(f"Unknown change_type: {change_type}")
            return False

    except Exception as e:
        logger.error(f"Error in process_inventory_adjustment: {str(e)}")
        db.session.rollback()
        return False


def _handle_additive_adjustment(item_id, quantity, change_type, unit, notes, created_by,
                               cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs):
    """Handle additive adjustments by creating new FIFO lots."""
    try:
        from ._fifo_ops import _internal_add_fifo_entry_enhanced

        item = db.session.get(InventoryItem, item_id)
        final_unit = unit or getattr(item, 'unit', 'count')

        # Use cost override if provided, otherwise use item's cost
        cost_per_unit = cost_override if cost_override is not None else item.cost_per_unit

        # Create new FIFO lot through FIFO service
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item_id,
            quantity=quantity,
            change_type=change_type,
            unit=final_unit,
            notes=notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            expiration_date=custom_expiration_date,
            shelf_life_days=custom_shelf_life_days,
            **kwargs
        )

        if not success:
            logger.error(f"FIFO lot creation failed: {error}")
            return False

        db.session.commit()
        record_audit_entry(item_id, change_type, notes or f'Added {quantity} {final_unit}')

        return True

    except Exception as e:
        logger.error(f"Error in additive adjustment: {str(e)}")
        db.session.rollback()
        return False


def _handle_deductive_adjustment(item_id, quantity, change_type, unit, notes, created_by, **kwargs):
    """Handle deductive adjustments using FIFO service for deduction planning."""
    try:
        from ._fifo_ops import (
            _calculate_deduction_plan_internal, 
            _execute_deduction_plan_internal,
            _record_deduction_plan_internal,
            calculate_current_fifo_total
        )

        item = db.session.get(InventoryItem, item_id)
        final_unit = unit or getattr(item, 'unit', 'count')

        # Get deduction plan from FIFO service
        deduction_plan, error = _calculate_deduction_plan_internal(
            item_id, abs(quantity), change_type
        )

        if error:
            logger.error(f"Deduction planning failed: {error}")
            return False

        if not deduction_plan:
            logger.warning(f"No deduction plan generated for {item_id}")
            return False

        # Execute deduction plan through FIFO service
        success, error = _execute_deduction_plan_internal(deduction_plan, item_id)
        if not success:
            logger.error(f"Deduction execution failed: {error}")
            return False

        # Record audit trail through FIFO service
        success = _record_deduction_plan_internal(
            item_id, deduction_plan, change_type, notes, 
            created_by=created_by, **kwargs
        )
        if not success:
            logger.error(f"Deduction recording failed")
            return False

        # Sync item quantity to FIFO total (authoritative source)
        current_fifo_total = calculate_current_fifo_total(item_id)
        item.quantity = current_fifo_total

        db.session.commit()
        record_audit_entry(item_id, change_type, notes or f'Deducted {abs(quantity)} {final_unit}')

        return True

    except Exception as e:
        logger.error(f"Error in deductive adjustment: {str(e)}")
        db.session.rollback()
        return False
