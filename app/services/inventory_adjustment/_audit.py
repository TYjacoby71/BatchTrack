
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
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

        # Route to correct history table based on item type
        if item.type == 'product':
            from app.models.product import ProductSKUHistory
            history = ProductSKUHistory(
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
        else:
            history = InventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=0.0,  # Audit entries don't change quantity
                remaining_quantity=0.0,  # Audit entries have no FIFO impact
                unit=unit or item.unit,
                note=notes,
                created_by=created_by,
                quantity_used=0.0,
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


def record_audit_entry(item_id, quantity, change_type, unit=None, notes=None, created_by=None, **kwargs):
    """
    Public helper for audit-only records (remaining_quantity=0, no inventory change)
    Used for tracking reservations, conversions, etc. without affecting FIFO
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False

        # Route to correct history table based on item type
        if item.type == 'product':
            from app.models.product import ProductSKUHistory
            history = ProductSKUHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=0.0,  # Audit entries don't change quantity
                remaining_quantity=0.0,  # Audit entries have no FIFO impact
                unit=unit or item.unit,
                notes=notes,
                created_by=created_by,
                organization_id=current_user.organization_id if current_user.is_authenticated else item.organization_id,
                **kwargs
            )
        else:
            history = InventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=0.0,  # Audit entries don't change quantity
                remaining_quantity=0.0,  # Audit entries have no FIFO impact
                unit=unit or item.unit,
                note=notes,
                created_by=created_by,
                quantity_used=0.0,
                organization_id=current_user.organization_id if current_user.is_authenticated else item.organization_id,
                **kwargs
            )

        db.session.add(history)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating audit entry: {str(e)}")
        return False
