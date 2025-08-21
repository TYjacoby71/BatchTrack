
"""
Additive operations handler - operations that increase inventory quantity.
These handlers calculate what needs to happen and return deltas.
They should NEVER directly modify item.quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

def handle_restock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle restock operations - adding new inventory.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"RESTOCK: Adding {quantity} to item {item.id}")
        
        # Use item's unit if not specified in kwargs
        unit = kwargs.get('unit') or item.unit or 'count'
        
        # Use provided cost or item's default cost
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Create FIFO entry (lot)
        success, message, lot_id = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create FIFO entry: {message}", 0

        # Record additive event in unified history (events-only, link to created lot)
        history_event = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit,
            unit_cost=float(final_cost) if final_cost is not None else 0.0,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,
            affected_lot_id=lot_id,
            fifo_code=None
        )
        db.session.add(history_event)

        # Return delta for core to apply
        quantity_delta = float(quantity)
        logger.info(f"RESTOCK SUCCESS: Will increase item {item.id} by {quantity_delta}")
        return True, f"Restocked {quantity} {unit}", quantity_delta

    except Exception as e:
        logger.error(f"Error in restock operation: {str(e)}")
        return False, f"Restock failed: {str(e)}", 0

def handle_manual_addition(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle manual additions - administrative inventory increases.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"MANUAL_ADDITION: Adding {quantity} to item {item.id}")
        
        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        success, message, lot_id = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create FIFO entry: {message}", 0

        # Record event linked to created lot
        history_event = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit,
            unit_cost=float(final_cost) if final_cost is not None else 0.0,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,
            affected_lot_id=lot_id,
            fifo_code=None
        )
        db.session.add(history_event)

        quantity_delta = float(quantity)
        return True, f"Manual addition of {quantity} {unit}", quantity_delta

    except Exception as e:
        logger.error(f"Error in manual addition: {str(e)}")
        return False, f"Manual addition failed: {str(e)}", 0

def handle_returned(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle returned items - items coming back into inventory.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"RETURNED: Adding {quantity} to item {item.id}")
        
        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        success, message, lot_id = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create FIFO entry: {message}", 0

        # Event
        history_event = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit,
            unit_cost=float(final_cost) if final_cost is not None else 0.0,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,
            affected_lot_id=lot_id,
            fifo_code=None
        )
        db.session.add(history_event)

        quantity_delta = float(quantity)
        return True, f"Returned {quantity} {unit} to inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in returned operation: {str(e)}")
        return False, f"Return failed: {str(e)}", 0

def handle_refunded(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle refunded items - items coming back from refunds.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"REFUNDED: Adding {quantity} to item {item.id}")
        
        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        success, message, lot_id = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create FIFO entry: {message}", 0

        # Event
        history_event = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit,
            unit_cost=float(final_cost) if final_cost is not None else 0.0,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,
            affected_lot_id=lot_id,
            fifo_code=None
        )
        db.session.add(history_event)

        quantity_delta = float(quantity)
        return True, f"Refunded {quantity} {unit} added to inventory", quantity_delta

    except Exception as e:
        logger.error(f"Error in refund operation: {str(e)}")
        return False, f"Refund failed: {str(e)}", 0

def handle_finished_batch(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle finished batch output - completed products added to inventory.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"FINISHED_BATCH: Adding {quantity} to item {item.id}")
        
        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        success, message, lot_id = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create FIFO entry: {message}", 0

        # Event
        history_event = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit,
            unit_cost=float(final_cost) if final_cost is not None else 0.0,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,
            affected_lot_id=lot_id,
            fifo_code=None
        )
        db.session.add(history_event)

        quantity_delta = float(quantity)
        return True, f"Finished batch added {quantity} {unit}", quantity_delta

    except Exception as e:
        logger.error(f"Error in finished batch operation: {str(e)}")
        return False, f"Finished batch failed: {str(e)}", 0
