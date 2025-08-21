"""
Inventory Adjustment Service - Canonical Entry Point

This service provides the single source of truth for all inventory adjustments
in BatchTrack. All inventory changes must go through process_inventory_adjustment.
"""

from ._core import process_inventory_adjustment
from ._handlers import OPERATION_HANDLERS, get_operation_handler

# Public API - only expose the canonical dispatcher
__all__ = ['process_inventory_adjustment']

# Operation registry for introspection
def get_supported_operations():
    """Return list of all supported operation types"""
    return list(OPERATION_HANDLERS.keys())