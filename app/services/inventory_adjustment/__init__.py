"""
Inventory Adjustment Service - Canonical Entry Point

This service provides the single source of truth for all inventory adjustments
in BatchTrack. All inventory changes must go through process_inventory_adjustment.
"""

from ._core import process_inventory_adjustment
from ._handlers import OPERATION_HANDLERS, get_operation_handler
from ._creation_logic import create_inventory_item
from ._edit_logic import update_inventory_item
from ._audit import record_audit_entry
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import credit_specific_lot

# Public API - expose the canonical functions needed by blueprints
__all__ = [
    'process_inventory_adjustment',
    'create_inventory_item', 
    'update_inventory_item',
    'record_audit_entry',
    'validate_inventory_fifo_sync',
    'credit_specific_lot'
]

# Operation registry for introspection
def get_supported_operations():
    """Return list of all supported operation types"""
    return list(OPERATION_HANDLERS.keys())