"""
Inventory Adjustment Service Package

This package is the canonical, single-source-of-truth for all inventory
and FIFO-related operations in the application.

All external modules (routes, other services, etc.) MUST import from this
__init__.py file. They are forbidden from importing from the internal
helper modules (those starting with an underscore).
"""

# Import the public functions from our internal helper modules
from ._core import process_inventory_adjustment
from ._edit_logic import update_inventory_item
from ._creation_logic import create_inventory_item
from ._validation import validate_inventory_fifo_sync
from ._audit import audit_event, record_audit_entry
from ._recount_logic import handle_recount_adjustment

def credit_specific_lot(item_id: int, fifo_entry_id: int, quantity: float, change_type: str = 'unreserved', notes: str = None, created_by: int = None):
    """
    Credit a specific FIFO lot back to inventory.
    Used primarily for reservation releases.
    """
    from app.models import db, UnifiedInventoryHistory

    try:
        # Find the FIFO entry to credit
        fifo_entry = UnifiedInventoryHistory.query.get(fifo_entry_id)
        if not fifo_entry:
            return False, f"FIFO entry {fifo_entry_id} not found"

        # Credit the quantity back to this specific lot
        fifo_entry.remaining_quantity = float(fifo_entry.remaining_quantity) + quantity

        # Create an audit record for the credit
        credit_record = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=change_type,
            quantity_change=quantity,
            remaining_quantity=0,  # This is a credit record, not a lot
            unit=fifo_entry.unit,
            unit_cost=fifo_entry.unit_cost,
            fifo_reference_id=fifo_entry.fifo_reference_id,
            fifo_code=fifo_entry.fifo_code,
            batch_id=fifo_entry.batch_id,
            notes=notes or f"Credit to lot {fifo_entry.fifo_reference_id}",
            created_by=created_by,
            quantity_used=0,
            is_perishable=fifo_entry.is_perishable,
            shelf_life_days=fifo_entry.shelf_life_days,
            expiration_date=fifo_entry.expiration_date,
            organization_id=fifo_entry.organization_id
        )

        db.session.add(credit_record)
        db.session.commit()

        return True, None

    except Exception as e:
        db.session.rollback()
        return False, str(e)


# Define what is public. Everything else is private.
__all__ = [
    'process_inventory_adjustment',
    'update_inventory_item',
    'create_inventory_item',
    'validate_inventory_fifo_sync',
    'audit_event',
    'record_audit_entry',
    'handle_recount_adjustment',
    'credit_specific_lot'
]


# Backwards compatibility shim for tests and legacy code
class InventoryAdjustmentService:
    """Backwards compatibility shim for tests and legacy code"""

    @staticmethod
    def adjust_inventory(*args, **kwargs):
        """Legacy method - use process_inventory_adjustment instead"""
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def process_inventory_adjustment(*args, **kwargs):
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def validate_inventory_fifo_sync(*args, **kwargs):
        return validate_inventory_fifo_sync(*args, **kwargs)

    @staticmethod
    def record_audit_entry(*args, **kwargs):
        return record_audit_entry(*args, **kwargs)

    # Add the new function to the backwards compatibility shim
    @staticmethod
    def credit_specific_lot(*args, **kwargs):
        return credit_specific_lot(*args, **kwargs)