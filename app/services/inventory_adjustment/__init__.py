"""
Inventory Adjustment Service - Centralized inventory operations
All inventory changes must go through process_inventory_adjustment()
"""

from ._core import process_inventory_adjustment
from ._creation_logic import create_inventory_item
from ._edit_logic import update_inventory_item
from ._validation import validate_inventory_fifo_sync

# Export the main functions
__all__ = [
    "process_inventory_adjustment",
    "validate_inventory_fifo_sync",
    "create_inventory_item",
    "update_inventory_item",
]
