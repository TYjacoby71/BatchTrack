import logging
from typing import Optional

from app.models import db, UnifiedInventoryHistory, InventoryItem

logger = logging.getLogger(__name__)


def weighted_unit_cost_for_batch_item(inventory_item_id: int, batch_id: int) -> float:
    """
    Compute the weighted-average unit cost of all negative inventory history events
    recorded for a given (batch_id, inventory_item_id).

    This is DRY and method-agnostic: it relies on the already-posted event unit_costs,
    which reflect either FIFO lot costs or the moving average cost depending on the
    organization's selected method and (for batches) the locked method at start.
    """
    try:
        if not inventory_item_id or not batch_id:
            return 0.0

        # Aggregate negative (deductive) entries for this batch+item
        events = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == inventory_item_id,
            UnifiedInventoryHistory.batch_id == batch_id,
            UnifiedInventoryHistory.quantity_change < 0
        ).all()

        if not events:
            # Fallback to current item moving average if no events yet
            item = db.session.get(InventoryItem, inventory_item_id)
            return float(item.cost_per_unit or 0.0) if item else 0.0

        total_qty = 0.0
        total_cost = 0.0
        for e in events:
            qty = abs(float(e.quantity_change or 0.0))
            unit_cost = float(e.unit_cost or 0.0)
            total_qty += qty
            total_cost += qty * unit_cost

        if total_qty <= 0:
            item = db.session.get(InventoryItem, inventory_item_id)
            return float(item.cost_per_unit or 0.0) if item else 0.0

        return total_cost / total_qty
    except Exception as ex:
        logger.error(f"Error computing weighted unit cost for item {inventory_item_id} in batch {batch_id}: {ex}")
        try:
            item = db.session.get(InventoryItem, inventory_item_id)
            return float(item.cost_per_unit or 0.0) if item else 0.0
        except Exception:
            return 0.0


# New: organization-agnostic weighted average cost for an inventory item based on active lots
def weighted_average_cost_for_item(inventory_item_id: int) -> float:
    """
    Compute the quantity-weighted average unit cost across all active lots
    (remaining_quantity > 0) for the given inventory item.

    This returns 0.0 if the item is missing or there are no active lots.
    """
    try:
        if not inventory_item_id:
            return 0.0

        item = db.session.get(InventoryItem, int(inventory_item_id))
        if not item:
            return 0.0

        # Import locally to avoid circular imports
        from app.models.inventory_lot import InventoryLot
        from sqlalchemy import and_

        lots = (
            InventoryLot.query
            .filter(
                and_(
                    InventoryLot.inventory_item_id == item.id,
                    InventoryLot.organization_id == item.organization_id,
                    InventoryLot.remaining_quantity > 0
                )
            )
            .all()
        )

        if not lots:
            return float(item.cost_per_unit or 0.0)

        total_qty = 0.0
        total_cost = 0.0
        for lot in lots:
            qty = float(lot.remaining_quantity or 0.0)
            if qty <= 0:
                continue
            unit_cost = float(lot.unit_cost or 0.0)
            total_qty += qty
            total_cost += qty * unit_cost

        return (total_cost / total_qty) if total_qty > 0 else float(item.cost_per_unit or 0.0)
    except Exception as ex:
        logger.error(f"Error computing weighted average cost for item {inventory_item_id}: {ex}")
        try:
            item = db.session.get(InventoryItem, int(inventory_item_id))
            return float(item.cost_per_unit or 0.0) if item else 0.0
        except Exception:
            return 0.0
