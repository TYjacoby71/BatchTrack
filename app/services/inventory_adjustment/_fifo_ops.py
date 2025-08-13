
import logging
from datetime import datetime
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.fifo_generator import generate_fifo_code

logger = logging.getLogger(__name__)

def identify_lots(item_id):
    """
    Identify consumable lots for an inventory item.
    Lots are FIFO entries where:
    - quantity_change > 0 (additive)
    - remaining_quantity > 0 (still has consumable inventory)
    - Initially: remaining_quantity == quantity_change (hasn't been consumed from)
    
    Returns list of lot entries ordered by timestamp (FIFO)
    """
    lots = UnifiedInventoryHistory.query.filter(
        UnifiedInventoryHistory.inventory_item_id == item_id,
        UnifiedInventoryHistory.quantity_change > 0,  # Only additive entries
        UnifiedInventoryHistory.remaining_quantity > 0  # Has remaining consumable quantity
    ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()
    
    return lots


def identify_refillable_lots(item_id):
    """
    Identify lots that can be refilled during recount operations.
    These are additive entries where remaining_quantity < original quantity_change.
    
    Returns list of (lot_entry, available_capacity) tuples
    """
    lots = UnifiedInventoryHistory.query.filter(
        UnifiedInventoryHistory.inventory_item_id == item_id,
        UnifiedInventoryHistory.quantity_change > 0  # Only additive entries
    ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()
    
    refillable_lots = []
    for lot in lots:
        original_qty = float(lot.quantity_change)
        current_remaining = float(lot.remaining_quantity)
        available_capacity = original_qty - current_remaining
        
        if available_capacity > 0:
            refillable_lots.append((lot, available_capacity))
    
    return refillable_lots


def _calculate_deduction_plan_internal(item_id, required_quantity, change_type='use'):
    """
    Calculates a deduction plan from available FIFO lots.
    Only operates on consumable lots (positive quantity_change with remaining_quantity > 0).
    Returns a list of tuples: [(entry_id, quantity_to_deduct, unit_cost), ...]
    """
    available_lots = identify_lots(item_id)
    
    deduction_plan = []
    remaining_needed = float(required_quantity)
    total_available = sum(float(lot.remaining_quantity) for lot in available_lots)

    if total_available < remaining_needed:
        return None, f"Insufficient inventory: need {remaining_needed}, available {total_available}"

    for lot in available_lots:
        if remaining_needed <= 0:
            break
        deduct_from_lot = min(float(lot.remaining_quantity), remaining_needed)
        deduction_plan.append((lot.id, deduct_from_lot, lot.unit_cost))
        remaining_needed -= deduct_from_lot

    return deduction_plan, None


def _calculate_addition_plan_internal(item_id, quantity_to_add, change_type='restock'):
    """
    Calculates an addition plan for refilling existing lots during recount.
    Returns list of (lot_id, fill_amount) tuples and remaining overflow quantity.
    """
    refillable_lots = identify_refillable_lots(item_id)
    
    addition_plan = []
    remaining_to_add = float(quantity_to_add)
    
    for lot, available_capacity in refillable_lots:
        if remaining_to_add <= 0:
            break
            
        fill_amount = min(remaining_to_add, available_capacity)
        if fill_amount > 0:
            addition_plan.append((lot.id, fill_amount))
            remaining_to_add -= fill_amount
    
    return addition_plan, remaining_to_add


def _execute_deduction_plan_internal(deduction_plan, item_id):
    """
    Executes a deduction plan against FIFO lots.
    Decrements remaining_quantity on each affected lot.
    """
    for entry_id, deduct_quantity, _ in deduction_plan:
        entry = db.session.get(UnifiedInventoryHistory, entry_id)
        if entry:
            entry.remaining_quantity = float(entry.remaining_quantity) - deduct_quantity
    return True, None


def _execute_addition_plan_internal(addition_plan, item_id):
    """
    Executes an addition plan against FIFO lots.
    Increments remaining_quantity on each affected lot.
    """
    for entry_id, add_quantity in addition_plan:
        entry = db.session.get(UnifiedInventoryHistory, entry_id)
        if entry:
            entry.remaining_quantity = float(entry.remaining_quantity) + add_quantity
    return True, None


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, **kwargs):
    """
    Creates audit trail entries for a deduction from lots.
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
            remaining_quantity=0.0,  # Deduction entries are not lots
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


def _record_addition_plan_internal(item_id, addition_plan, change_type, notes, **kwargs):
    """
    Creates audit trail entries for additions to existing lots.
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False

    for entry_id, qty_added in addition_plan:
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=qty_added,
            remaining_quantity=0.0,  # Addition entries are not new lots
            unit=item.unit,
            unit_cost=item.cost_per_unit,
            notes=f"{notes or 'Lot refill'} - Refilled lot {entry_id}",
            fifo_reference_id=entry_id,
            fifo_code=generate_fifo_code(change_type),
            created_by=kwargs.get('created_by'),
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
    Creates a new FIFO lot in the unified history table.
    Only creates lots for additive change types.
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, f"Item with ID {item_id} not found."

    try:
        # Prevent adding entries with zero or negative quantity
        if float(quantity) <= 0:
            logger.warning(f"Ignoring zero or negative quantity adjustment for item {item_id}: {quantity}")
            return True, None  # Treat as a successful no-op

        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=float(quantity),
            unit=unit or item.unit,
            remaining_quantity=float(quantity),  # New lot starts with full quantity
            unit_cost=cost_per_unit,
            notes=notes,
            fifo_code=generate_fifo_code(change_type, remaining_quantity=float(quantity)),
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

        # Update parent inventory item quantity
        from app.services.unit_conversion import ConversionEngine
        rounded_qty_change = ConversionEngine.round_value(float(quantity), 3)
        new_quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)

        logger.info(f"FIFO: Updating inventory item {item_id} quantity: {item.quantity} → {new_quantity}")
        item.quantity = new_quantity

        return True, None
    except TypeError as e:
        logger.error(f"Failed to add FIFO entry for item {item_id}: {e}")
        return False, str(e)
