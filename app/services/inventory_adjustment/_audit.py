# app/services/inventory_adjustment/_audit.py

import logging
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.fifo_generator import generate_fifo_code

logger = logging.getLogger(__name__)

def audit_event(item_id: int, change_type: str, notes: str = "", created_by: int = None, **kwargs) -> bool:
    """
    Creates a sanctioned, non-FIFO, audit-only history entry.
    This does NOT affect inventory quantity.
    """
    item = db.session.get(InventoryItem, item_id)
    if not item:
        logger.error(f"Audit event failed: Item {item_id} not found.")
        return False

    try:
        audit_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=0.0,
            remaining_quantity=0.0,
            unit=item.unit,
            notes=notes,
            created_by=created_by,
            fifo_code=generate_fifo_code(change_type),
            **kwargs
        )
        db.session.add(audit_entry)
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to create audit entry for item {item_id}: {e}")
        db.session.rollback()
        return False