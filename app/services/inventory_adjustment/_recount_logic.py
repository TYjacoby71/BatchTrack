# In app/services/inventory_adjustment/_recount_logic.py
import logging
from app.models import db, InventoryItem
from ._fifo_ops import _calculate_deduction_plan_internal, _execute_deduction_plan_internal, _record_deduction_plan_internal, _internal_add_fifo_entry_enhanced, _calculate_addition_plan_internal, _execute_addition_plan_internal, _record_addition_plan_internal
from ._validation import validate_inventory_fifo_sync

logger = logging.getLogger(__name__)

def handle_recount_adjustment(item_id, target_quantity, notes, created_by, item_type):
    """
    Handles a recount by calculating the delta and applying it by either
    refilling/creating new lots (increase) or deducting from existing lots (decrease).
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        raise ValueError(f"Recount failed: Item {item_id} not found.")

    # 1. Get the authoritative current total from all valid FIFO lots.
    _, _, _, current_fifo_total = validate_inventory_fifo_sync(item_id, item_type)

    delta = float(target_quantity) - current_fifo_total

    if abs(delta) < 0.001:
        item.quantity = current_fifo_total # Ensure sync even if no change
        db.session.commit()
        return True

    # --- 2. Apply the Delta using FIFO Helpers ---
    if delta > 0:
        # INCREASE: Refill existing lots first, then create an overflow lot.
        addition_plan, overflow = _calculate_addition_plan_internal(item_id, delta)

        if addition_plan:
            _execute_addition_plan_internal(addition_plan, item_id)
            _record_addition_plan_internal(item_id, addition_plan, 'recount_increase', notes or "Recount refill", created_by=created_by)

        if overflow > 0:
            _internal_add_fifo_entry_enhanced(
                item_id=item_id,
                quantity=overflow,
                change_type='recount_increase', # This is a new, true lot
                unit=item.unit,
                notes=notes or "Recount overflow",
                cost_per_unit=item.cost_per_unit,
                created_by=created_by
            )

    else: # delta < 0
        # DECREASE: Create and execute a deduction plan.
        to_deduct = abs(delta)
        deduction_plan, error = _calculate_deduction_plan_internal(item_id, to_deduct, 'recount_decrease')
        if error:
            raise ValueError(f"Recount decrease failed: {error}")

        _execute_deduction_plan_internal(deduction_plan, item_id)
        _record_deduction_plan_internal(item_id, deduction_plan, 'recount_decrease', notes or "Recount deduction", created_by=created_by)

    # --- 3. Final Sync ---
    # After all operations, the parent item's quantity MUST equal the new FIFO total.
    _, _, _, new_fifo_total = validate_inventory_fifo_sync(item_id, item_type)
    item.quantity = new_fifo_total
    db.session.commit()

    return True