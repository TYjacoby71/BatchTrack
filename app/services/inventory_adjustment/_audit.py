"""
Audit Trail Management for Inventory Adjustments

This module handles all audit trail and history recording for inventory operations.
"""

from datetime import datetime
from flask_login import current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.fifo_generator import generate_fifo_code
import logging

logger = logging.getLogger(__name__)


def audit_event(
    item_id: int,
    change_type: str,
    notes: str = "",
    created_by: int = None,
    item_type: str = "ingredient",
    fifo_reference_id: int = None,
    unit: str = None,
    unit_cost: float = None,
) -> bool:
    """
    Sanctioned audit-only history entry (no inventory change).
    Uses the same internal helpers so nothing writes outside this module.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False

        fifo_code = generate_fifo_code(change_type, 0)

        # Use unified history table for all audit entries
        history = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=change_type,
            quantity_change=0.0,  # Audit entries don't change quantity
            remaining_quantity=0.0,  # Audit entries have no FIFO impact
            unit=unit or item.unit,
            notes=notes,
            created_by=created_by,
            organization_id=current_user.organization_id if current_user.is_authenticated else item.organization_id,
            fifo_code=fifo_code,
            fifo_reference_id=fifo_reference_id,
            unit_cost=unit_cost
        )

        db.session.add(history)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating audit entry: {str(e)}")
        return False


def record_audit_entry(
    item_id: int,
    change_type: str,
    quantity_change: float = 0,
    notes: str | None = None,
    created_by: int | None = None,
    **kwargs
) -> bool:
    """
    Record an audit trail entry for inventory operations.

    This is used for operations that need to log activity but don't affect FIFO lots,
    such as cost overrides, administrative changes, etc.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            logger.error(f"Cannot record audit entry - item {item_id} not found")
            return False

        audit_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=float(quantity_change) if quantity_change is not None else None,
            remaining_quantity=0.0,  # Audit entries don't create FIFO lots
            unit=item.unit,
            notes=notes,
            created_by=created_by,
            fifo_code=generate_fifo_code(change_type),
            batch_id=kwargs.get('batch_id'),
            customer=kwargs.get('customer'),
            order_id=kwargs.get('order_id'),
            sale_price=kwargs.get('sale_price')
        )

        db.session.add(audit_entry)
        db.session.commit()

        logger.info(f"Recorded audit entry for item {item_id}: {change_type}")
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to record audit entry for item {item_id}: {str(e)}")
        return False