
"""
Centralized Operation Registry

Single source of truth for all inventory operations with their configurations and logic.
"""

from typing import Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# OPERATION TYPE REGISTRY - Single Source of Truth
# ============================================================================

OPERATION_REGISTRY = {
    # ADDITIVE OPERATIONS - Add inventory, create FIFO lots
    'restock': {
        'type': 'additive',
        'message': 'Restocked',
        'use_cost_override': True,
        'description': 'Add new stock with optional cost override'
    },
    'manual_addition': {
        'type': 'additive',
        'message': 'Added manually',
        'use_cost_override': False,
        'description': 'Manual inventory addition'
    },
    'returned': {
        'type': 'additive',
        'message': 'Returned',
        'use_cost_override': False,
        'description': 'Returned inventory'
    },
    'refunded': {
        'type': 'additive',
        'message': 'Refunded',
        'use_cost_override': False,
        'description': 'Refunded inventory'
    },
    'finished_batch': {
        'type': 'additive',
        'message': 'Added from finished batch',
        'use_cost_override': False,
        'description': 'Product created from batch completion'
    },
    'initial_stock': {
        'type': 'additive',
        'message': 'Initial stock created',
        'use_cost_override': True,
        'description': 'First-time inventory creation'
    },

    # DEDUCTIVE OPERATIONS - Remove inventory using FIFO
    'use': {
        'type': 'deductive',
        'message': 'Used',
        'description': 'General usage deduction'
    },
    'sale': {
        'type': 'deductive',
        'message': 'Sold',
        'description': 'Sales deduction'
    },
    'spoil': {
        'type': 'deductive',
        'message': 'Marked as spoiled',
        'description': 'Spoilage deduction'
    },
    'trash': {
        'type': 'deductive',
        'message': 'Trashed (recorded as spoiled)',
        'description': 'Trash deduction (recorded as spoil)'
    },
    'expired': {
        'type': 'deductive',
        'message': 'Removed (expired)',
        'description': 'Expiration deduction'
    },
    'damaged': {
        'type': 'deductive',
        'message': 'Removed (damaged)',
        'description': 'Damage deduction'
    },
    'quality_fail': {
        'type': 'deductive',
        'message': 'Removed (quality fail)',
        'description': 'Quality failure deduction'
    },
    'sample': {
        'type': 'deductive',
        'message': 'Used for sample',
        'description': 'Sample deduction'
    },
    'tester': {
        'type': 'deductive',
        'message': 'Used for tester',
        'description': 'Tester deduction'
    },
    'gift': {
        'type': 'deductive',
        'message': 'Gave as gift',
        'description': 'Gift deduction'
    },
    'reserved': {
        'type': 'deductive',
        'message': 'Reserved',
        'description': 'Reservation deduction'
    },
    'batch': {
        'type': 'deductive',
        'message': 'Used in batch',
        'description': 'Batch ingredient deduction'
    },

    # SPECIAL OPERATIONS - Non-FIFO operations with custom logic
    'recount': {
        'type': 'special',
        'message': 'Recount completed',
        'description': 'Sophisticated recount with FIFO lot filling'
    },
    'cost_override': {
        'type': 'special',
        'message': 'Cost updated',
        'description': 'Update cost per unit without quantity change'
    },
    'unit_conversion': {
        'type': 'special',
        'message': 'Unit conversion completed',
        'description': 'Convert units without quantity change'
    }
}


def get_operation_config(change_type: str) -> Dict[str, Any]:
    """Get configuration for an operation type"""
    return OPERATION_REGISTRY.get(change_type, {})


def get_operation_type(change_type: str) -> str:
    """Get the operation type (additive, deductive, special)"""
    config = get_operation_config(change_type)
    return config.get('type', 'unknown')


def is_additive_operation(change_type: str) -> bool:
    """Check if operation adds inventory"""
    return get_operation_type(change_type) == 'additive'


def is_deductive_operation(change_type: str) -> bool:
    """Check if operation removes inventory"""
    return get_operation_type(change_type) == 'deductive'


def is_special_operation(change_type: str) -> bool:
    """Check if operation is special (non-FIFO)"""
    return get_operation_type(change_type) == 'special'


def get_all_operation_types() -> list:
    """Get all supported operation types"""
    return list(OPERATION_REGISTRY.keys())


def validate_operation_type(change_type: str) -> bool:
    """Validate if operation type is supported"""
    return change_type in OPERATION_REGISTRY
