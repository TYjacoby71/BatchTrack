"""
FIFO Service - Compatibility Shim
This file now redirects all calls to the canonical inventory adjustment service.
"""

from app.services.inventory_adjustment import process_inventory_adjustment


class FIFOService:
    """Compatibility shim - all methods redirect to canonical inventory adjustment service"""

    @staticmethod
    def deduct_fifo(*args, **kwargs):
        """Legacy method - use process_inventory_adjustment instead"""
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def calculate_deduction_plan(item_id, quantity, change_type='use'):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _calculate_deduction_plan_internal
        return _calculate_deduction_plan_internal(item_id, quantity, change_type)

    @staticmethod
    def execute_deduction_plan(deduction_plan, item_id):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _execute_deduction_plan_internal
        return _execute_deduction_plan_internal(deduction_plan, item_id)

    @staticmethod
    def record_deduction_plan(item_id, deduction_plan, change_type, notes, **kwargs):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _record_deduction_plan_internal
        return _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, **kwargs)

    @staticmethod
    def _internal_add_fifo_entry(*args, **kwargs):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _internal_add_fifo_entry_enhanced
        return _internal_add_fifo_entry_enhanced(*args, **kwargs)


# Legacy function for backwards compatibility
def deduct_inventory_fifo(*args, **kwargs):
    """Legacy function - use process_inventory_adjustment instead"""
    return process_inventory_adjustment(*args, **kwargs)