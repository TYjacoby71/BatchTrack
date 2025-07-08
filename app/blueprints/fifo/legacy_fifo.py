
"""
Legacy FIFO functions - deprecated, use FIFOService instead
This module provides backwards compatibility while we migrate to the new FIFOService
"""

from .services import FIFOService
import warnings

def get_fifo_entries(inventory_item_id, include_expired=False):
    """DEPRECATED: Use FIFOService.get_fifo_entries instead"""
    warnings.warn(
        "get_fifo_entries is deprecated. Use FIFOService.get_fifo_entries instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return FIFOService.get_fifo_entries(inventory_item_id, include_expired)

def get_expired_fifo_entries(inventory_item_id):
    """DEPRECATED: Use FIFOService.get_expired_fifo_entries instead"""
    warnings.warn(
        "get_expired_fifo_entries is deprecated. Use FIFOService.get_expired_fifo_entries instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return FIFOService.get_expired_fifo_entries(inventory_item_id)

def deduct_fifo(inventory_item_id, quantity, change_type, notes=None, **kwargs):
    """DEPRECATED: Use FIFOService.calculate_deduction_plan + execute_deduction_plan instead"""
    warnings.warn(
        "deduct_fifo is deprecated. Use FIFOService.calculate_deduction_plan + execute_deduction_plan instead.",
        DeprecationWarning,
        stacklevel=2
    )
    deduction_plan = FIFOService.calculate_deduction_plan(inventory_item_id, quantity)
    if deduction_plan:
        return FIFOService.execute_deduction_plan(
            inventory_item_id, deduction_plan, change_type, notes, **kwargs
        )
    return False

def recount_fifo(inventory_item_id, new_quantity, notes=None, **kwargs):
    """DEPRECATED: Use FIFOService.recount_fifo instead"""
    warnings.warn(
        "recount_fifo is deprecated. Use FIFOService.recount_fifo instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return FIFOService.recount_fifo(inventory_item_id, new_quantity, notes, **kwargs)
