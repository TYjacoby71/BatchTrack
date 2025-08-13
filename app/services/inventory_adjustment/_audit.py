
import logging
from datetime import datetime
from app.models import db, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)

def log_inventory_adjustment(item_id, adjustment_type, quantity_change, notes, created_by):
    """
    Log an inventory adjustment for audit purposes.
    
    Args:
        item_id: ID of the inventory item
        adjustment_type: Type of adjustment made
        quantity_change: Quantity that was changed (positive for additions, negative for deductions)
        notes: Notes about the adjustment
        created_by: User ID who made the adjustment
    """
    try:
        # Create audit log entry
        audit_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=f"audit_{adjustment_type}",
            quantity_changed=quantity_change,
            remaining_quantity=0,  # Not applicable for audit entries
            notes=f"AUDIT: {adjustment_type} - {notes or 'No notes'}",
            created_by=created_by,
            created_at=TimezoneUtils.utc_now(),
            cost_per_unit=0,  # Not applicable for audit entries
            organization_id=None  # Will be set by the model if needed
        )
        
        db.session.add(audit_entry)
        
        logger.info(f"Logged inventory adjustment: item={item_id}, type={adjustment_type}, "
                   f"change={quantity_change}, user={created_by}")
        
    except Exception as e:
        logger.error(f"Failed to log inventory adjustment: {e}")
        # Don't raise exception - audit logging shouldn't break the main operation
