"""
Additive operations handler - operations that increase inventory quantity.
These handlers calculate what needs to happen and return deltas.
They should NEVER directly modify item.quantity.
"""

import logging
from app.models import db, UnifiedInventoryHistory
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

def _universal_additive_handler(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Universal handler for all additive operations.
    Consolidates logic for restock, manual_addition, returned, refunded, and finished_batch.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"{change_type.upper()}: Adding {quantity} to item {item.id}")

        # Use item's unit if not specified in kwargs
        unit = kwargs.get('unit') or item.unit or 'count'

        # Use provided cost or item's default cost
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Create FIFO entry (lot) with proper source tracking
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

        # Only create history event for restock - others are handled by _internal_add_fifo_entry_enhanced
        if change_type == 'restock':
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

        # Generate appropriate success message
        action_messages = {
            'restock': f"Restocked {quantity} {unit}",
            'manual_addition': f"Manual addition of {quantity} {unit}",
            'returned': f"Returned {quantity} {unit} to inventory",
            'refunded': f"Refunded {quantity} {unit} added to inventory",
            'finished_batch': f"Finished batch added {quantity} {unit}"
        }

        success_message = action_messages.get(change_type, f"{change_type.replace('_', ' ').title()} added {quantity} {unit}")

        logger.info(f"{change_type.upper()} SUCCESS: Will increase item {item.id} by {quantity_delta}")
        return True, success_message, quantity_delta

    except Exception as e:
        logger.error(f"Error in {change_type} operation: {str(e)}")
        return False, f"{change_type.replace('_', ' ').title()} failed: {str(e)}", 0

# Individual handler functions for backwards compatibility
def handle_restock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """Handle restock operations - adding new inventory."""
    return _universal_additive_handler(item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)

def handle_manual_addition(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """Handle manual additions - administrative inventory increases."""
    return _universal_additive_handler(item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)

def handle_returned(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """Handle returned items - items coming back into inventory."""
    return _universal_additive_handler(item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)

def handle_refunded(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """Handle refunded items - items coming back from refunds."""
    return _universal_additive_handler(item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)

def handle_finished_batch(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """Handle finished batch output - completed products added to inventory."""
    return _universal_additive_handler(item, quantity, change_type, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, **kwargs)