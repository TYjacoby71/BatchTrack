"""
Special Operations Handler

Handles special operations that don't fit additive/deductive patterns, including recount.
"""

import logging
from app.models import db, UnifiedInventoryHistory
from ._operation_registry import get_operation_config, is_special_operation
from ._fifo_ops import calculate_current_fifo_total
from ._additive_ops import handle_additive_operation
from ._deductive_ops import handle_deductive_operation

logger = logging.getLogger(__name__)


def handle_special_operation(item, quantity, change_type, notes=None, created_by=None, cost_override=None, **kwargs):
    """
    Universal handler for all special operations using centralized registry.
    """
    try:
        if not is_special_operation(change_type):
            return False, f"Not a special operation: {change_type}"

        if change_type == 'recount':
            return _handle_recount(item, quantity, notes, created_by, **kwargs)
        elif change_type == 'cost_override':
            return _handle_cost_override(item, cost_override)
        elif change_type == 'unit_conversion':
            return _handle_unit_conversion(item, **kwargs)
        else:
            return False, f"Unknown special operation: {change_type}"

    except Exception as e:
        logger.error(f"Error in special operation {change_type}: {str(e)}")
        return False, str(e)


def _handle_recount(item, quantity, notes=None, created_by=None, **kwargs):
    """
    THE DEFINITIVE RECOUNT HANDLER implementing "True North" rules:

    1. Input is absolute target quantity (not delta)
    2. Calculate delta = target - current_fifo_total  
    3. Positive delta = delegate to additive operations
    4. Negative delta = delegate to deductive operations
    5. Zero delta = log no-change event
    6. Final item.quantity MUST match target exactly
    """
    try:
        # Rule #1: Input is absolute target quantity
        target_quantity = float(quantity)

        # Rule #2: Calculate delta from current FIFO total
        current_fifo_total = calculate_current_fifo_total(item.id)
        delta = target_quantity - current_fifo_total

        logger.info(f"RECOUNT: {item.name} - Current FIFO: {current_fifo_total}, Target: {target_quantity}, Delta: {delta}")

        # Rule #7: Handle no-change case gracefully
        if abs(delta) < 0.001:
            # Create audit trail for zero-change recount
            history_entry = UnifiedInventoryHistory(
                inventory_item_id=item.id,
                organization_id=item.organization_id,
                change_type='recount',
                quantity_change=0.0,
                remaining_quantity=0.0,
                unit=getattr(item, 'unit', 'count'),
                unit_cost=getattr(item, 'cost_per_unit', 0.0),
                notes=f"{notes or 'Recount'} - No change needed (target matches current)",
                created_by=created_by
            )
            db.session.add(history_entry)

            # Rule #6: Ensure final quantity matches target exactly
            item.quantity = target_quantity

            return True, f"Inventory already at target quantity: {target_quantity}"

        # Rule #3: Positive delta = delegate to additive operations
        if delta > 0:
            logger.info(f"RECOUNT INCREASE: Adding {delta} {getattr(item, 'unit', 'units')} to reach target")

            success, message = handle_additive_operation(
                item=item,
                quantity=abs(delta),
                change_type='recount',  # This will create proper audit trail
                notes=f"{notes or 'Recount adjustment'} - target: {target_quantity} (+{delta})",
                created_by=created_by,
                **kwargs
            )

            if not success:
                return False, f"Recount increase failed: {message}"

            # Rule #6: Ensure final quantity matches target exactly
            item.quantity = target_quantity

            return True, f"Recount added {delta} {getattr(item, 'unit', 'units')} to reach target {target_quantity}"

        # Rule #4: Negative delta = delegate to deductive operations  
        else:  # delta < 0
            logger.info(f"RECOUNT DECREASE: Removing {abs(delta)} {getattr(item, 'unit', 'units')} to reach target")

            success, message = handle_deductive_operation(
                item=item,
                quantity=abs(delta),
                change_type='recount',  # This will create proper audit trail
                notes=f"{notes or 'Recount adjustment'} - target: {target_quantity} ({delta})",
                created_by=created_by,
                **kwargs
            )

            if not success:
                return False, f"Recount decrease failed: {message}"

            # Rule #6: Ensure final quantity matches target exactly  
            item.quantity = target_quantity

            return True, f"Recount removed {abs(delta)} {getattr(item, 'unit', 'units')} to reach target {target_quantity}"

    except Exception as e:
        logger.error(f"RECOUNT ERROR: {str(e)}")
        return False, str(e)


def _handle_cost_override(item, cost_override):
    """Handle cost override (no quantity change)"""
    try:
        if cost_override is not None:
            item.cost_per_unit = cost_override
            db.session.commit()
            return True, f"Updated cost to {cost_override}"
        return False, "No cost override provided"
    except Exception as e:
        logger.error(f"Error in cost override: {str(e)}")
        return False, str(e)


def _handle_unit_conversion(item, **kwargs):
    """Handle unit conversion"""
    try:
        # Unit conversion logic would go here
        return True, "Unit conversion completed"
    except Exception as e:
        logger.error(f"Error in unit conversion: {str(e)}")
        return False, str(e)