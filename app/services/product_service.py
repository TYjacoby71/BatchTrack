from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory, InventoryItem
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from flask_login import current_user
from ..utils.fifo_generator import generate_fifo_id

class ProductService:
    @staticmethod
    def get_product_summary_skus():
        """Get summary of all products with their total quantities"""
        # Group by product_name and aggregate quantities
        product_summaries = db.session.query(
            ProductSKU.product_name,
            ProductSKU.product_base_unit,
            func.sum(ProductSKU.current_quantity).label('total_quantity'),
            func.count(ProductSKU.id).label('sku_count'),
            func.min(ProductSKU.low_stock_threshold).label('low_stock_threshold'),
            func.max(ProductSKU.last_updated).label('last_updated')
        ).filter(
            ProductSKU.is_active == True,
            ProductSKU.is_product_active == True
        ).group_by(
            ProductSKU.product_name,
            ProductSKU.product_base_unit
        ).all()

        products = []
        for summary in product_summaries:
            products.append({
                'product_name': summary.product_name,
                'product_base_unit': summary.product_base_unit,
                'total_quantity': float(summary.total_quantity or 0),
                'sku_count': summary.sku_count,
                'low_stock_threshold': float(summary.low_stock_threshold or 0),
                'last_updated': summary.last_updated
            })

        return products

    @staticmethod
    def get_or_create_sku(product_name, variant_name, size_label, unit=None, sku_code=None, variant_description=None):
        """Get existing SKU or create new one with automatic SKU generation"""
        # Check if SKU already exists
        sku = ProductSKU.query.filter_by(
            product_name=product_name,
            variant_name=variant_name,
            size_label=size_label
        ).first()

        if sku:
            # If SKU exists but doesn't have a code, generate one
            if not sku.sku_code or sku.sku_code.strip() == '':
                sku.sku_code = ProductService.generate_sku_code(product_name, variant_name, size_label)
                db.session.flush()
            return sku

        # Always generate SKU code automatically
        if not sku_code:
            sku_code = ProductService.generate_sku_code(product_name, variant_name, size_label)

        # Get product base unit from existing SKUs
        existing_sku = ProductSKU.query.filter_by(product_name=product_name).first()
        product_base_unit = existing_sku.product_base_unit if existing_sku else (unit or 'g')

        # Create new SKU
        sku = ProductSKU(
            product_name=product_name,
            product_base_unit=product_base_unit,
            variant_name=variant_name,
            size_label=size_label,
            unit=unit or product_base_unit,
            sku_code=sku_code,
            variant_description=variant_description
        )

        db.session.add(sku)
        db.session.flush()
        return sku

    @staticmethod
    def ensure_base_variant_if_needed(product_name):
        """Create a Base variant if no variants exist for a product"""
        existing_skus = ProductSKU.query.filter_by(
            product_name=product_name,
            is_active=True
        ).all()

        if not existing_skus:
            # No variants exist, create a Base variant
            base_sku = ProductService.get_or_create_sku(
                product_name=product_name,
                variant_name='Base',
                size_label='Bulk'
            )
            return base_sku
        return None

    @staticmethod
    def backfill_missing_sku_codes():
        """Generate SKU codes for any SKUs that don't have them"""
        skus_without_codes = ProductSKU.query.filter(
            ProductSKU.sku_code.is_(None),
            ProductSKU.is_active == True
        ).all()

        for sku in skus_without_codes:
            sku.sku_code = ProductService.generate_sku_code(
                sku.product_name, 
                sku.variant_name, 
                sku.size_label
            )

        if skus_without_codes:
            db.session.commit()
            return len(skus_without_codes)
        return 0

    @staticmethod
    def generate_sku_code(product_name, variant_name, size_label):
        """Generate a unique SKU code based on product components"""
        # Create base SKU from first 3 characters of each component
        product_part = ''.join(c for c in product_name[:3].upper() if c.isalnum())
        variant_part = ''.join(c for c in variant_name[:2].upper() if c.isalnum())  
        size_part = ''.join(c for c in size_label[:3].upper() if c.isalnum())

        # Ensure we have at least some characters from each part
        product_part = product_part[:3].ljust(2, 'X')
        variant_part = variant_part[:2].ljust(2, 'X')
        size_part = size_part[:3].ljust(2, 'X')

        base_sku = f"{product_part}-{variant_part}-{size_part}"

        # Check for uniqueness by querying for existing SKUs with the same base
        count = 1
        unique_sku_code = base_sku
        while ProductSKU.query.filter(ProductSKU.sku_code == unique_sku_code).first():
            unique_sku_code = f"{base_sku}-{count}"
            count += 1

        return unique_sku_code

    @staticmethod
    def get_fifo_inventory_groups(product_name):
        """Get FIFO inventory groups for a product (legacy compatibility)"""
        # Get all SKUs for the product
        skus = ProductSKU.query.filter_by(
            product_name=product_name,
            is_active=True
        ).filter(ProductSKU.current_quantity > 0).all()

        groups = []
        for sku in skus:
            groups.append({
                'sku_id': sku.id,
                'variant_name': sku.variant_name,
                'size_label': sku.size_label,
                'quantity': sku.current_quantity,
                'unit': sku.unit,
                'unit_cost': sku.unit_cost,
                'expiration_date': sku.expiration_date,
                'fifo_id': sku.fifo_id
            })

        return groups

    @staticmethod
    def add_product_from_batch(batch_id: int, sku_id: int, quantity: float) -> bool:
        """Add product inventory from a completed batch"""
        try:
            batch = Batch.query.get_or_404(batch_id)
            sku = ProductSKU.query.get_or_404(sku_id)

            # Create FIFO entry
            fifo_entry = InventoryItem(
                sku_id=sku_id,
                quantity=quantity,
                batch_id=batch_id,
                batch_cost_per_unit=batch.total_cost / quantity if batch.total_cost and quantity > 0 else None,
                is_perishable=batch.is_perishable,
                shelf_life_days=batch.shelf_life_days,
                expiration_date=batch.expiration_date,
                notes=f'Added from batch {batch.label_code}',
                fifo_id=generate_fifo_id()
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
            db.session.flush()
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
            sku = ProductSKU.query.get_or_404(sku_id)

            if sku.current_quantity < quantity:
                return False  # Insufficient stock

            remaining_to_deduct = quantity
            old_quantity = sku.current_quantity

            # Get FIFO entries ordered by timestamp
            fifo_entries = InventoryItem.query.filter_by(sku_id=sku_id)\
                .filter(InventoryItem.quantity > 0)\
                .order_by(InventoryItem.timestamp).all()

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
            db.session.flush()
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
            db.session.flush()
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
        return ProductService.get_product_summary_skus()

    @staticmethod
    def get_low_stock_skus(threshold_multiplier: float = 1.0):
        """Get SKUs that are low on stock"""
        return ProductSKU.query.filter(
            ProductSKU.current_quantity <= ProductSKU.low_stock_threshold * threshold_multiplier,
            ProductSKU.is_active == True
        ).all()