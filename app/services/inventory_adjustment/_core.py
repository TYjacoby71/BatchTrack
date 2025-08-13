# app/services/inventory_adjustment/_core.py

import logging
from datetime import datetime
from flask_login import current_user
from app.models import db, InventoryItem
from ._validation import validate_inventory_fifo_sync
from ._recount_logic import handle_recount_adjustment
from ._fifo_ops import _calculate_deduction_plan_internal, _execute_deduction_plan_internal, _record_deduction_plan_internal, _internal_add_fifo_entry_enhanced, _calculate_addition_plan_internal, _execute_addition_plan_internal, _record_addition_plan_internal
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)

def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str | None = None,
    notes: str | None = None,
    created_by: int | None = None,
    cost_override: float | None = None,
    **kwargs,
) -> bool:
    """
    Canonical entry point for ALL inventory adjustments.
    Delegates to specialized handlers for different operations.
    """
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            logger.error(f"Adjustment failed: InventoryItem with ID {item_id} not found.")
            return False

        # --- Scoping Check ---
        if current_user.is_authenticated and item.organization_id != current_user.organization_id:
            logger.warning(f"User {current_user.id} permission denied for item {item_id}.")
            return False

        # --- Handle Special Cases First ---
        if change_type == 'recount':
            return handle_recount_adjustment(item.id, quantity, notes, created_by, item.type)

        # --- Normalize Inputs ---
        final_unit = unit or item.unit
        converted_quantity = quantity
        if final_unit and item.unit and final_unit != item.unit:
            conversion = safe_convert(quantity, final_unit, item.unit, ingredient_id=item.id)
            if not conversion["ok"]:
                raise ValueError(f"Unit conversion failed: {conversion['error']}")
            converted_quantity = conversion["result"]["converted_value"]

        # --- Determine Operation Type ---
        additive_types = {'restock', 'manual_add', 'returned', 'refunded', 'recount_increase', 'unreserved'}
        deductive_types = {'spoil', 'trash', 'expired', 'gift', 'sample', 'tester', 'quality_fail', 'damaged', 'sold', 'sale', 'use', 'batch', 'reserved', 'recount_decrease'}

        if change_type in additive_types:
            success = _handle_additive_adjustment(item, converted_quantity, change_type, final_unit, notes, created_by, cost_override, **kwargs)
        elif change_type in deductive_types:
            success = _handle_deductive_adjustment(item, converted_quantity, change_type, final_unit, notes, created_by, **kwargs)
        else:
            logger.error(f"Invalid change_type '{change_type}' for item {item_id}.")
            return False

        if not success:
            db.session.rollback()
            return False

        # --- Final Sync and Commit ---
        _, _, _, final_fifo_total = validate_inventory_fifo_sync(item_id, item.type)
        item.quantity = ConversionEngine.round_value(final_fifo_total, 3)
        db.session.commit()
        return True

    except Exception as e:
        logger.error(f"Error in process_inventory_adjustment for item {item_id}: {e}", exc_info=True)
        db.session.rollback()
        return False

def _handle_additive_adjustment(item, quantity, change_type, unit, notes, created_by, cost_override, **kwargs):
    """Handles operations that add inventory by creating a new FIFO lot."""
    cost = cost_override if cost_override is not None else item.cost_per_unit
    success, error = _internal_add_fifo_entry_enhanced(
        item_id=item.id,
        quantity=quantity,
        change_type=change_type,
        unit=unit,
        notes=notes,
        cost_per_unit=cost,
        created_by=created_by,
        **kwargs
    )
    if not success:
        raise ValueError(f"Failed to create FIFO lot: {error}")
    return True

def _handle_deductive_adjustment(item, quantity, change_type, unit, notes, created_by, **kwargs):
    """Handles operations that deduct inventory by consuming from FIFO lots."""
    deduction_plan, error = _calculate_deduction_plan_internal(item.id, abs(quantity), change_type)
    if error:
        raise ValueError(f"Failed to create deduction plan: {error}")

    _execute_deduction_plan_internal(deduction_plan, item.id)
    _record_deduction_plan_internal(item.id, deduction_plan, change_type, notes, created_by=created_by, **kwargs)
    return True