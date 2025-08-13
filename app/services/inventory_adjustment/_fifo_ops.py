
import logging
from datetime import datetime
from app.models import db, InventoryItem
from app.models.unified_inventory_history import UnifiedInventoryHistory
from app.utils.fifo_generator import generate_fifo_code

logger = logging.getLogger(__name__)

def _calculate_deduction_plan_internal(item_id, required_quantity, change_type='use'):
    """
    Calculates a deduction plan from available FIFO lots in the unified history.
    Returns a list of tuples: [(entry_id, quantity_to_deduct, unit_cost), ...]
    """
    # This now queries the single, unified history table.
    available_entries = UnifiedInventoryHistory.query.filter(
        UnifiedInventoryHistory.inventory_item_id == item_id,
        UnifiedInventoryHistory.remaining_quantity > 0
    ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

    deduction_plan = []
    remaining_needed = float(required_quantity)
    total_available = sum(float(e.remaining_quantity) for e in available_entries)

    if total_available < remaining_needed:
        return None, f"Insufficient inventory: need {remaining_needed}, available {total_available}"

    for entry in available_entries:
        if remaining_needed <= 0:
            break
        deduct_from_entry = min(float(entry.remaining_quantity), remaining_needed)
        deduction_plan.append((entry.id, deduct_from_entry, entry.unit_cost))
        remaining_needed -= deduct_from_entry

    return deduction_plan, None


def _execute_deduction_plan_internal(deduction_plan, item_id):
    """
    Executes a deduction plan against the unified history table.
    """
    for entry_id, deduct_quantity, _ in deduction_plan:
        entry = db.session.get(UnifiedInventoryHistory, entry_id)
        if entry:
            entry.remaining_quantity = float(entry.remaining_quantity) - deduct_quantity
    # The commit will be handled by the main service function
    return True, None


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, **kwargs):
    """
    Creates audit trail entries for a deduction from the unified history table.
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False

    for entry_id, qty_deducted, unit_cost in deduction_plan:
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=-abs(qty_deducted),
            remaining_quantity=0.0, # Deduction entries are not lots
            unit=item.unit,
            unit_cost=unit_cost,
            notes=notes,
            fifo_reference_id=entry_id,
            fifo_code=generate_fifo_code(change_type),
            batch_id=kwargs.get('batch_id'),
            created_by=kwargs.get('created_by'),
            customer=kwargs.get('customer'),
            sale_price=kwargs.get('sale_price'),
            order_id=kwargs.get('order_id'),
        )
        db.session.add(history_entry)
    return True


def _internal_add_fifo_entry_enhanced(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str | None,
    notes: str | None,
    cost_per_unit: float | None,
    **kwargs,
) -> tuple[bool, str | None]:
    """
    Robustly creates a new FIFO lot in the unified history table.
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, f"Item with ID {item_id} not found."

    try:
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit or item.unit,
            remaining_quantity=float(quantity),
            unit_cost=cost_per_unit,
            notes=notes,
            fifo_code=generate_fifo_code(change_type),
            batch_id=kwargs.get("batch_id"),
            created_by=kwargs.get("created_by"),
            customer=kwargs.get("customer"),
            sale_price=kwargs.get("sale_price"),
            order_id=kwargs.get("order_id"),
            is_perishable=item.is_perishable,
            shelf_life_days=kwargs.get("shelf_life_days") or item.shelf_life_days,
            expiration_date=kwargs.get("expiration_date"),
        )
        db.session.add(history_entry)
        # The commit and parent item quantity update will be handled by the main service function
        return True, None
    except TypeError as e:
        logger.error(f"Failed to add FIFO entry for item {item_id}: {e}")
        return False, str(e)
