"""
FIFO Service - Compatibility Shim
This file now redirects all calls to the canonical inventory adjustment service.
"""

from app.services.inventory_adjustment import process_inventory_adjustment
from app.services.inventory_adjustment._fifo_ops import get_item_lots as _get_item_lots


class FIFOService:
    """Compatibility shim - all methods redirect to canonical inventory adjustment service"""

    @staticmethod
    def deduct_fifo(item_id, change_type, quantity, notes=None, created_by=None):
        """Legacy method - use process_inventory_adjustment instead"""
        return process_inventory_adjustment(item_id, change_type, quantity, notes, created_by)

    @staticmethod
    def calculate_deduction_plan(item_id, quantity, change_type='use'):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment._fifo_ops import calculate_fifo_deduction_plan
        return calculate_fifo_deduction_plan(item_id, quantity, change_type)

    @staticmethod
    def execute_deduction_plan(deduction_plan, item_id):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment._fifo_ops import execute_fifo_deduction_plan
        return execute_fifo_deduction_plan(deduction_plan, item_id)

    @staticmethod
    def record_deduction_plan(item_id, deduction_plan, change_type, notes, created_by=None):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment._fifo_ops import create_fifo_deduction_audit_trail
        return create_fifo_deduction_audit_trail(item_id, deduction_plan, change_type, notes, created_by)

    @staticmethod
    def _internal_add_fifo_entry(inventory_item_id, quantity, change_type, notes="", unit=None, cost_per_unit=None, created_by=None, batch_id=None, expiration_date=None, shelf_life_days=None):
        """Legacy method - use process_inventory_adjustment instead"""
        from app.services.inventory_adjustment._fifo_ops import create_new_fifo_lot
        return create_new_fifo_lot(
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

    @staticmethod
    def get_active_lots(item_id: int, active_only: bool = True):
        """Return lots for an item via FIFO service (authoritative source)."""
        return _get_item_lots(item_id=item_id, active_only=active_only, order='desc')


# Legacy function for backwards compatibility
def deduct_inventory_fifo(item_id, change_type, quantity, notes=None, created_by=None):
    """Legacy function - use process_inventory_adjustment instead"""
    return process_inventory_adjustment(item_id, change_type, quantity, notes, created_by)