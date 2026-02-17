"""Inventory FIFO validation helpers.

Synopsis:
Validate inventory quantities against FIFO lot totals.

Glossary:
- FIFO sync: Match between inventory quantity and lot totals.
- Validation: Check performed before committing adjustments.
"""

import logging
from app.models import db, InventoryItem
from app.services.quantity_base import from_base_quantity
from sqlalchemy import and_
from app.utils.permissions import has_tier_permission

logger = logging.getLogger(__name__)


# --- FIFO sync validation ---
# Purpose: Validate inventory quantity against FIFO totals.
def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    Validate that inventory quantity matches FIFO totals using proper InventoryLot model.
    This ensures the item.quantity field stays in sync with actual lot quantities.
    """
    from app.models.inventory_lot import InventoryLot
    
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, "Item not found", 0, 0

    org_tracks_quantities = has_tier_permission(
        "batches.track_inventory_outputs",
        organization=getattr(item, "organization", None),
        default_if_missing_catalog=True,
    )
    effective_tracking_enabled = bool(getattr(item, "is_tracked", True)) and org_tracks_quantities
    if not effective_tracking_enabled:
        inventory_qty = from_base_quantity(
            base_amount=int(getattr(item, "quantity_base", 0) or 0),
            unit_name=item.unit,
            ingredient_id=item.id,
            density=item.density,
        )
        return True, None, inventory_qty, inventory_qty

    # Get all active lots for this item with proper organization scoping
    active_lots = InventoryLot.query.filter(
        and_(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.organization_id == item.organization_id,
            InventoryLot.remaining_quantity_base > 0
        )
    ).all()

    # Calculate total from actual lot quantities
    fifo_total_base = sum(int(lot.remaining_quantity_base or 0) for lot in active_lots)
    inventory_qty_base = int(getattr(item, "quantity_base", 0) or 0)
    is_valid = inventory_qty_base == fifo_total_base

    fifo_total = from_base_quantity(
        base_amount=fifo_total_base,
        unit_name=item.unit,
        ingredient_id=item.id,
        density=item.density,
    )
    inventory_qty = from_base_quantity(
        base_amount=inventory_qty_base,
        unit_name=item.unit,
        ingredient_id=item.id,
        density=item.density,
    )

    if not is_valid:
        logger.error(f"FIFO SYNC MISMATCH for item {item_id} ({item.name}):")
        logger.error(f"  Item quantity: {inventory_qty}")
        logger.error(f"  FIFO total: {fifo_total}")
        logger.error(f"  Difference: {abs(inventory_qty - fifo_total)}")
        logger.error(f"  Active FIFO lots: {len(active_lots)}")
        
        # Log individual FIFO lots for debugging
        for i, lot in enumerate(active_lots):
            logger.error(f"    Lot {i+1}: {lot.remaining_quantity} ({lot.source_type}, {lot.received_date})")
        
        error_msg = f"FIFO sync error: inventory={inventory_qty}, fifo_total={fifo_total}, diff={abs(inventory_qty - fifo_total)}"
        return False, error_msg, inventory_qty, fifo_total

    return True, None, inventory_qty, fifo_total
