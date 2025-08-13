
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
from ._recount_logic import handle_recount_adjustment
from ._validation import validate_inventory_fifo_sync
from ._audit import audit_event, record_audit_entry

# Define what is public. Everything else is private.
__all__ = [
    'process_inventory_adjustment',
    'update_inventory_item', 
    'validate_inventory_fifo_sync',
    'audit_event',
    'record_audit_entry',
    'handle_recount_adjustment'
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
