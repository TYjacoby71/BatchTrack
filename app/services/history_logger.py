
from datetime import datetime
from flask_login import current_user
from ..models import db, InventoryHistory, ProductSKUHistory
from ..utils.fifo_generator import generate_fifo_id

class HistoryLogger:
    """Centralized service for logging inventory and product SKU history"""
    
    @staticmethod
    def record_inventory_history(
        inventory_item_id,
        change_type,
        quantity_change,
        unit,
        remaining_quantity=0,
        unit_cost=None,
        notes=None,
        fifo_reference_id=None,
        fifo_code=None,
        batch_id=None,
        quantity_used=0.0,
        used_for_batch_id=None,
        expiration_date=None,
        shelf_life_days=None,
        is_perishable=False,
        created_by=None
    ):
        """Record raw inventory history entry"""
        history = InventoryHistory(
            inventory_item_id=inventory_item_id,
            change_type=change_type,
            quantity_change=quantity_change,
            unit=unit or 'count',
            remaining_quantity=remaining_quantity,
            unit_cost=unit_cost,
            note=notes,
            fifo_reference_id=fifo_reference_id,
            fifo_code=fifo_code,
            batch_id=batch_id,
            quantity_used=quantity_used,
            used_for_batch_id=used_for_batch_id,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            expiration_date=expiration_date,
            created_by=created_by or (current_user.id if current_user.is_authenticated else None),
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )
        db.session.add(history)
        return history
    
    @staticmethod
    def record_product_sku_history(
        sku_id,
        change_type,
        quantity_change,
        unit,
        remaining_quantity=0,
        unit_cost=None,
        notes=None,
        fifo_reference_id=None,
        fifo_code=None,
        batch_id=None,
        customer=None,
        sale_price=None,
        order_id=None,
        expiration_date=None,
        shelf_life_days=None,
        is_perishable=False,
        created_by=None
    ):
        """Record product SKU history entry"""
        history = ProductSKUHistory(
            sku_id=sku_id,
            change_type=change_type,
            quantity_change=quantity_change,
            unit=unit,
            remaining_quantity=remaining_quantity,
            unit_cost=unit_cost,
            notes=notes,
            fifo_reference_id=fifo_reference_id,
            fifo_code=fifo_code,
            batch_id=batch_id,
            customer=customer,
            sale_price=sale_price,
            order_id=order_id,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            expiration_date=expiration_date,
            created_by=created_by or (current_user.id if current_user.is_authenticated else None),
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )
        db.session.add(history)
        return history
