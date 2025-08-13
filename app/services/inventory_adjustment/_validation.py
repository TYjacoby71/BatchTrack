
import logging
from app.models import InventoryItem, UnifiedInventoryHistory
from app.services.unit_conversion import ConversionEngine
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    Validate that inventory quantity matches FIFO totals with proper rounding.
    Returns (is_valid, error_msg, inventory_qty, fifo_total)
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            logger.error(f"Validation failed: Item {item_id} not found")
            return False, "Item not found", 0.0, 0.0

        # Get sum of remaining quantities from FIFO entries (only positive lots)
        fifo_entries = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == item_id,
                UnifiedInventoryHistory.remaining_quantity > 0
            )
        ).all()

        # Calculate totals with proper rounding
        fifo_total = ConversionEngine.round_value(
            sum(float(entry.remaining_quantity or 0) for entry in fifo_entries), 3
        )
        inventory_qty = ConversionEngine.round_value(float(item.quantity or 0), 3)

        # Allow small floating point differences
        tolerance = 0.001
        difference = abs(inventory_qty - fifo_total)
        is_valid = difference < tolerance

        if not is_valid:
            error_msg = (
                f"FIFO sync error for item {item_id} ({item.name}): "
                f"inventory={inventory_qty}, fifo_total={fifo_total}, "
                f"diff={ConversionEngine.round_value(difference, 6)}"
            )
            logger.warning(error_msg)
            return False, error_msg, inventory_qty, fifo_total

        logger.debug(f"FIFO sync valid for item {item_id}: inventory={inventory_qty}, fifo={fifo_total}")
        return True, None, inventory_qty, fifo_total
    
    except Exception as e:
        logger.error(f"Error during FIFO validation for item {item_id}: {e}")
        return False, f"Validation error: {str(e)}", 0.0, 0.0
