"""
Inventory Adjustment Service - Canonical Entry Point

This service provides the single source of truth for all inventory adjustments
in BatchTrack. All inventory changes must go through process_inventory_adjustment.
"""

from ._core import process_inventory_adjustment
from ._creation_logic import create_inventory_item
from ._edit_logic import update_inventory_item
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import credit_specific_lot

# Import operation modules to get supported operations
from ._additive_ops import ADDITIVE_OPERATION_GROUPS
from ._deductive_ops import DEDUCTION_DESCRIPTIONS
from ._special_ops import handle_cost_override, handle_unit_conversion
from ._recount_logic import handle_recount

# Public API - expose the canonical functions needed by blueprints
__all__ = [
    'process_inventory_adjustment',
    'create_inventory_item', 
    'update_inventory_item',
    'validate_inventory_fifo_sync',
    'credit_specific_lot'
]

# Operation registry for introspection
def get_supported_operations():
    """Return list of all supported operation types"""
    operations = []
    
    # Add all additive operations
    for group_config in ADDITIVE_OPERATION_GROUPS.values():
        operations.extend(group_config['operations'])
    
    # Add all deductive operations
    operations.extend(DEDUCTION_DESCRIPTIONS.keys())
    
    # Add special operations
    operations.extend(['recount', 'cost_override', 'unit_conversion', 'initial_stock'])
    
    return operations