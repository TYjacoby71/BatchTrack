# app/services/inventory_adjustment/__init__.py

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
from ._validation import validate_inventory_fifo_sync
from ._audit import audit_event
from ._fifo_ops import credit_specific_lot

# Define what is public. Everything else is private.
__all__ = [
    'process_inventory_adjustment',
    'update_inventory_item',
    'validate_inventory_fifo_sync',
    'audit_event',
    'credit_specific_lot'
]