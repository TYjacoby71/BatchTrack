from datetime import datetime
from typing import Optional, List, Dict
from flask_login import current_user
from sqlalchemy import func, desc, asc

from ..models import db, ProductSKU, ProductSKUHistory
from ..services.inventory_adjustment import generate_fifo_code

class ProductInventoryService:
    """Product inventory service - mirrors raw inventory system with SKU+History only"""

    @staticmethod
    def add_stock(sku_id: int, quantity: float, unit_cost: float = 0, 
                  batch_id: Optional[int] = None, container_id: Optional[int] = None,
                  notes: str = '', change_type: str = 'manual_addition') -> ProductSKUHistory:
        """Add stock to SKU - creates FIFO history entry like InventoryHistory"""

        sku = ProductSKU.query.get_or_404(sku_id)
        old_quantity = sku.current_quantity
        new_quantity = old_quantity + quantity

        # Update SKU current quantity
        sku.current_quantity = new_quantity
        sku.last_updated = datetime.utcnow()

        # Create FIFO history entry (like InventoryHistory with remaining_quantity)
        history = ProductSKUHistory(
            sku_id=sku_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=quantity,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            remaining_quantity=quantity,  # For FIFO tracking
            original_quantity=quantity,
            unit=sku.unit,
            unit_cost=unit_cost,
            batch_id=batch_id,
            container_id=container_id,
            fifo_code=generate_fifo_code(f"SKU{sku_id}"),
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None
        )

        db.session.add(history)
        return history

    @staticmethod
    def deduct_stock(sku_id: int, quantity: float, change_type: str = 'manual_deduction',
                     notes: str = '', sale_price: Optional[float] = None,
                     customer: Optional[str] = None) -> bool:
        """Deduct stock using FIFO - mirrors raw inventory deduct_fifo"""

        sku = ProductSKU.query.get_or_404(sku_id)

        if sku.current_quantity < quantity:
            return False  # Insufficient stock

        # Get FIFO entries with remaining quantity (like InventoryHistory)
        fifo_entries = ProductSKUHistory.query.filter_by(sku_id=sku_id)\
            .filter(ProductSKUHistory.remaining_quantity > 0)\
            .order_by(ProductSKUHistory.timestamp.asc()).all()

        # Check if enough stock available
        total_available = sum(entry.remaining_quantity for entry in fifo_entries)
        if total_available < quantity:
            return False

        remaining_to_deduct = quantity
        old_quantity = sku.current_quantity

        # Execute FIFO deductions
        for entry in fifo_entries:
            if remaining_to_deduct <= 0:
                break

            deduct_amount = min(entry.remaining_quantity, remaining_to_deduct)
            entry.remaining_quantity -= deduct_amount
            remaining_to_deduct -= deduct_amount

        # Update SKU total
        sku.current_quantity = old_quantity - quantity
        sku.last_updated = datetime.utcnow()

        # Create deduction history entry
        history = ProductSKUHistory(
            sku_id=sku_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=-quantity,
            old_quantity=old_quantity,
            new_quantity=sku.current_quantity,
            remaining_quantity=0,  # Deductions don't have remaining
            unit=sku.unit,
            sale_price=sale_price,
            customer=customer,
            fifo_code=generate_fifo_code(f"SKU{sku_id}"),
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None
        )

        db.session.add(history)
        return True

    @staticmethod
    def recount_sku(sku_id: int, new_quantity: float, notes: str = '') -> bool:
        """Recount SKU inventory - mirrors raw inventory recount"""

        sku = ProductSKU.query.get_or_404(sku_id)
        old_quantity = sku.current_quantity
        difference = new_quantity - old_quantity

        if difference == 0:
            return True

        if difference < 0:
            # Reduce stock using FIFO
            return ProductInventoryService.deduct_stock(
                sku_id=sku_id,
                quantity=abs(difference),
                change_type='recount',
                notes=f"Recount adjustment: {old_quantity} → {new_quantity}. {notes}"
            )
        else:
            # Add stock
            ProductInventoryService.add_stock(
                sku_id=sku_id,
                quantity=difference,
                change_type='recount',
                notes=f"Recount adjustment: {old_quantity} → {new_quantity}. {notes}"
            )
            return True

    @staticmethod
    def adjust_fifo_entry(history_id: int, quantity: float, change_type: str,
                         notes: str = '') -> bool:
        """Adjust specific FIFO entry - like adjusting InventoryHistory"""

        history_entry = ProductSKUHistory.query.get_or_404(history_id)
        sku = ProductSKU.query.get_or_404(history_entry.sku_id)

        original_remaining = history_entry.remaining_quantity

        if change_type == 'recount':
            # Set new remaining for this entry
            quantity_change = quantity - original_remaining
            history_entry.remaining_quantity = max(0, quantity)
        else:
            # Deduction from this specific entry
            if quantity > original_remaining:
                return False  # Can't deduct more than available
            quantity_change = -quantity
            history_entry.remaining_quantity = max(0, original_remaining - quantity)

        # Update SKU total
        sku.current_quantity += quantity_change
        sku.last_updated = datetime.utcnow()

        # Create adjustment history entry
        adjustment_history = ProductSKUHistory(
            sku_id=history_entry.sku_id,
            timestamp=datetime.utcnow(),
            change_type=f'fifo_{change_type}',
            quantity_change=quantity_change,
            old_quantity=sku.current_quantity - quantity_change,
            new_quantity=sku.current_quantity,
            remaining_quantity=0,
            unit=sku.unit,
            fifo_code=generate_fifo_code(f"SKU{history_entry.sku_id}"),
            notes=f"FIFO entry #{history_id} adjustment: {original_remaining} → {history_entry.remaining_quantity}. {notes}",
            created_by=current_user.id if current_user.is_authenticated else None
        )

        db.session.add(adjustment_history)
        return True

    @staticmethod
    def get_sku_history(sku_id: int, page: int = 1, per_page: int = 50) -> dict:
        """Get paginated history for SKU"""

        history_query = ProductSKUHistory.query.filter_by(sku_id=sku_id)\
            .order_by(ProductSKUHistory.timestamp.desc())

        pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'items': pagination.items,
            'pagination': pagination,
            'total': pagination.total
        }

    @staticmethod
    def get_fifo_entries(sku_id: int, active_only: bool = False):
        """Get FIFO entries for SKU - from history entries with remaining_quantity"""
        query = ProductSKUHistory.query.filter_by(sku_id=sku_id)

        if active_only:
            query = query.filter(ProductSKUHistory.remaining_quantity > 0)
        else:
            # Show entries that were additions (have remaining_quantity field populated)
            query = query.filter(ProductSKUHistory.original_quantity.isnot(None))

        return query.order_by(ProductSKUHistory.timestamp.asc()).all()

    @staticmethod
    def get_all_skus_summary() -> List[Dict]:
        """Get summary of all SKUs with current quantities"""
        skus = ProductSKU.query.filter_by(is_active=True).all()

        summary = []
        for sku in skus:
            summary.append({
                'sku_id': sku.id,
                'product_name': sku.product_name,
                'variant_name': sku.variant_name,
                'size_label': sku.size_label,
                'sku_code': sku.sku_code,
                'current_quantity': sku.current_quantity,
                'unit': sku.unit,
                'low_stock_threshold': sku.low_stock_threshold,
                'is_low_stock': sku.current_quantity <= sku.low_stock_threshold
            })

        return summary