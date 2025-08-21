"""
FIFO Service - Compatibility Shim
This file now redirects all calls to the canonical inventory adjustment service.
"""

from app.services.inventory_adjustment import process_inventory_adjustment


class FIFOService:
    """Compatibility shim - all methods redirect to canonical inventory adjustment service"""

    @staticmethod
    def deduct_fifo(item_id, change_type, quantity, notes=None, created_by=None):
        """Legacy method - use process_inventory_adjustment instead"""
        return process_inventory_adjustment(item_id, change_type, quantity, notes, created_by)

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
    def record_deduction_plan(item_id, deduction_plan, change_type, notes, created_by=None):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _record_deduction_plan_internal
        return _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, created_by)

    @staticmethod
    def _internal_add_fifo_entry(inventory_item_id, quantity, change_type, notes="", unit=None, cost_per_unit=None, created_by=None, batch_id=None, expiration_date=None, shelf_life_days=None):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment import _internal_add_fifo_entry_enhanced
        return _internal_add_fifo_entry_enhanced(
            item_id=inventory_item_id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            custom_expiration_date=expiration_date,
            custom_shelf_life_days=shelf_life_days,
            batch_id=batch_id
        )


# Legacy function for backwards compatibility
def deduct_inventory_fifo(item_id, change_type, quantity, notes=None, created_by=None):
    """Legacy function - use process_inventory_adjustment instead"""
    return process_inventory_adjustment(item_id, change_type, quantity, notes, created_by)