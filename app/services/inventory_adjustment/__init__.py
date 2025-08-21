
"""
Inventory Adjustment Service - Canonical Entry Point

Consolidated service using centralized operation registry and simplified handlers.
"""

from ._core import process_inventory_adjustment
from ._operation_registry import (
    get_operation_config, 
    get_all_operation_types, 
    validate_operation_type,
    is_additive_operation,
    is_deductive_operation, 
    is_special_operation
)
from ._creation_logic import create_inventory_item
from ._edit_logic import update_inventory_item
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import credit_specific_lot

# Public API
__all__ = [
    'process_inventory_adjustment',
    'create_inventory_item',
    'update_inventory_item', 
    'validate_inventory_fifo_sync',
    'credit_specific_lot',
    'get_all_operation_types',
    'validate_operation_type'
]

# Simplified operation registry access
def get_supported_operations():
    """Return list of all supported operation types"""
    return get_all_operation_types()
