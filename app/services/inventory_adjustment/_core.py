
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
            return False

        # Check if this is an initial stock case (item with no FIFO history)
        if _is_initial_stock_case(item_id):
            logger.info(f"INITIAL STOCK: Detected item {item_id} has no FIFO history, delegating to creation logic")
            return _handle_initial_stock_via_creation_logic(
                item_id, quantity, change_type, unit, notes, created_by,
                cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs
            )

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


def _is_initial_stock_case(item_id: int) -> bool:
    """Check if item has no existing FIFO history."""
    return UnifiedInventoryHistory.query.filter_by(inventory_item_id=item_id).count() == 0


def _handle_initial_stock_via_creation_logic(
    item_id: int, quantity: float, change_type: str, unit: str = None,
    notes: str = None, created_by: int = None, cost_override: float = None,
    custom_expiration_date=None, custom_shelf_life_days: int = None, **kwargs
) -> bool:
    """
    Handle initial stock by using the same logic as create_inventory_item.
    This ensures consistent FIFO setup for new items.
    """
    try:
        from ._creation_logic import create_inventory_item
        
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False

        # If quantity is 0, just create a history entry noting initial creation
        if quantity == 0:
            logger.info(f"Creating initial zero-stock entry for item {item_id}")
            history_entry = UnifiedInventoryHistory(
                inventory_item_id=item_id,
                change_type='item_created',
                quantity_change=0.0,
                unit=unit or item.unit or 'count',
                unit_cost=cost_override or item.cost_per_unit or 0.0,
                remaining_quantity=0.0,
                notes=notes or 'Initial item creation - no stock added',
                created_by=created_by,
                is_perishable=item.is_perishable or False,
                shelf_life_days=custom_shelf_life_days or item.shelf_life_days,
                expiration_date=custom_expiration_date
            )
            db.session.add(history_entry)
            db.session.commit()
            record_audit_entry(item_id, 'item_created', 'Initial creation with zero stock')
            return True

        # For non-zero quantities, prepare form data that matches creation logic
        form_data = {
            'name': item.name,
            'quantity': str(quantity),
            'unit': unit or item.unit or 'count',
            'type': item.type or 'ingredient',
            'cost_entry_type': 'per_unit',
            'cost_per_unit': str(cost_override or item.cost_per_unit or 0),
            'low_stock_threshold': str(item.low_stock_threshold or 0),
            'is_perishable': 'on' if item.is_perishable else '',
            'shelf_life_days': str(custom_shelf_life_days or item.shelf_life_days or 0),
            'notes': notes or 'Initial stock via adjustment',
            'storage_amount': str(item.storage_amount or 0),
            'storage_unit': item.storage_unit or '',
        }

        # Delete the existing empty item to avoid duplicate name conflict
        db.session.delete(item)
        db.session.flush()

        # Use creation logic to properly set up the item with FIFO
        success, message, new_item_id = create_inventory_item(
            form_data, item.organization_id, created_by or 1
        )

        if success:
            logger.info(f"Initial stock setup completed via creation logic: item {new_item_id}")
            return True
        else:
            logger.error(f"Creation logic failed: {message}")
            db.session.rollback()
            return False

    except Exception as e:
        logger.error(f"Error in initial stock via creation logic: {str(e)}")
        db.session.rollback()
        return False
