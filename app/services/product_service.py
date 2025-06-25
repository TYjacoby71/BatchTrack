from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory, Batch
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from flask_login import current_user

class ProductService:
    @staticmethod
    def get_or_create_sku(
        product_name: str, 
        variant_name: str = 'Base', 
        size_label: str = 'Bulk',
        unit: str = 'oz',
        sku_code: str = None,
        variant_description: str = None
    ) -> ProductSKU:
        """Get existing SKU or create new one"""

        # Check if SKU already exists
        sku = ProductSKU.query.filter_by(
            product_name=product_name,
            variant_name=variant_name,
            size_label=size_label
        ).first()

        if sku:
            return sku

        # Get product_base_unit from existing SKUs or use default
        existing_sku = ProductSKU.query.filter_by(product_name=product_name).first()
        product_base_unit = existing_sku.product_base_unit if existing_sku else unit

        # Create new SKU
        sku = ProductSKU(
            product_name=product_name,
            product_base_unit=product_base_unit,
            variant_name=variant_name,
            variant_description=variant_description,
            size_label=size_label,
            unit=unit,
            sku_code=sku_code,
            current_quantity=0.0,
            low_stock_threshold=0.0,
            is_active=True,
            is_product_active=True,
            created_by=current_user.id if current_user.is_authenticated else None,
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )

        db.session.add(sku)
        db.session.flush()  # Get the ID
        return sku

    @staticmethod
    def add_product_from_batch(batch_id: int, sku_id: int, quantity: float) -> bool:
        """Add product inventory from a completed batch"""
        try:
            from ..models import ProductInventory

            batch = Batch.query.get_or_404(batch_id)
            sku = ProductSKU.query.get_or_404(sku_id)

            # Create FIFO entry
            fifo_entry = ProductInventory(
                sku_id=sku_id,
                quantity=quantity,
                batch_id=batch_id,
                batch_cost_per_unit=batch.total_cost / quantity if batch.total_cost and quantity > 0 else None,
                is_perishable=batch.is_perishable,
                shelf_life_days=batch.shelf_life_days,
                expiration_date=batch.expiration_date,
                notes=f'Added from batch {batch.label_code}'
            )

            db.session.add(fifo_entry)

            # Update SKU total quantity
            sku.current_quantity += quantity
            sku.last_updated = datetime.utcnow()

            # Create history record
            history = ProductSKUHistory(
                sku_id=sku_id,
                timestamp=datetime.utcnow(),
                change_type='batch_completion',
                quantity_change=quantity,
                old_quantity=sku.current_quantity - quantity,
                new_quantity=sku.current_quantity,
                batch_id=batch_id,
                notes=f'Added from completed batch {batch.label_code}',
                created_by=current_user.id if current_user.is_authenticated else None
            )

            db.session.add(history)
            return fifo_entry

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def deduct_stock(
        sku_id: int, 
        quantity: float, 
        change_type: str = 'manual_deduction',
        sale_price: float = None,
        customer: str = None,
        notes: str = ''
    ) -> bool:
        """Deduct stock from SKU using FIFO"""
        try:
            from ..models import ProductInventory

            sku = ProductSKU.query.get_or_404(sku_id)

            if sku.current_quantity < quantity:
                return False  # Insufficient stock

            remaining_to_deduct = quantity
            old_quantity = sku.current_quantity

            # Get FIFO entries ordered by timestamp
            fifo_entries = ProductInventory.query.filter_by(sku_id=sku_id)\
                .filter(ProductInventory.quantity > 0)\
                .order_by(ProductInventory.timestamp).all()

            # Deduct from FIFO entries
            for entry in fifo_entries:
                if remaining_to_deduct <= 0:
                    break

                deduction_from_entry = min(entry.quantity, remaining_to_deduct)
                entry.quantity -= deduction_from_entry
                remaining_to_deduct -= deduction_from_entry

            # Update SKU quantity
            sku.current_quantity -= quantity
            sku.last_updated = datetime.utcnow()

            # Create history record
            history = ProductSKUHistory(
                sku_id=sku_id,
                timestamp=datetime.utcnow(),
                change_type=change_type,
                quantity_change=-quantity,
                old_quantity=old_quantity,
                new_quantity=sku.current_quantity,
                sale_price=sale_price,
                customer=customer,
                notes=notes,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            db.session.add(history)
            return True

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def recount_sku(sku_id: int, new_quantity: float, notes: str = '') -> bool:
        """Process a recount adjustment for a specific SKU"""
        try:
            sku = ProductSKU.query.get_or_404(sku_id)
            old_quantity = sku.current_quantity
            quantity_change = new_quantity - old_quantity

            if quantity_change == 0:
                return True  # No change needed

            # Update SKU quantity
            sku.current_quantity = max(0, new_quantity)
            sku.last_updated = datetime.utcnow()

            # Create history record
            history = ProductSKUHistory(
                sku_id=sku_id,
                timestamp=datetime.utcnow(),
                change_type='recount',
                quantity_change=quantity_change,
                old_quantity=old_quantity,
                new_quantity=sku.current_quantity,
                notes=notes,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            db.session.add(history)
            return True

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def search_skus(search_term: str):
        """Search SKUs by product name, variant, or size label"""
        search_pattern = f"%{search_term}%"
        return ProductSKU.query.filter(
            db.or_(
                ProductSKU.product_name.ilike(search_pattern),
                ProductSKU.variant_name.ilike(search_pattern),
                ProductSKU.size_label.ilike(search_pattern),
                ProductSKU.sku_code.ilike(search_pattern)
            ),
            ProductSKU.is_active == True
        ).order_by(
            ProductSKU.product_name,
            ProductSKU.variant_name
        ).all()

    @staticmethod
    def get_products_summary():
        """Get summary of all products grouped by product name"""
        # Get all active SKUs grouped by product name
        skus = ProductSKU.query.filter_by(is_active=True, is_product_active=True).all()

        products = {}
        for sku in skus:
            if sku.product_name not in products:
                products[sku.product_name] = {
                    'name': sku.product_name,
                    'base_unit': sku.product_base_unit,
                    'total_quantity': 0,
                    'variant_count': 0,
                    'sku_count': 0,
                    'is_active': sku.is_product_active
                }

            products[sku.product_name]['total_quantity'] += sku.current_quantity
            products[sku.product_name]['sku_count'] += 1

        # Count unique variants per product
        for product_name in products:
            variant_count = len(set(sku.variant_name for sku in skus if sku.product_name == product_name))
            products[product_name]['variant_count'] = variant_count

        return list(products.values())

    @staticmethod
    def get_low_stock_skus(threshold_multiplier: float = 1.0):
        """Get SKUs that are low on stock"""
        return ProductSKU.query.filter(
            ProductSKU.current_quantity <= ProductSKU.low_stock_threshold * threshold_multiplier,
            ProductSKU.is_active == True
        ).all()