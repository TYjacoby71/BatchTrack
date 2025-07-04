from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory
from datetime import datetime
from typing import Optional, Dict, List, Tuple

class ProductService:
    @staticmethod
    def get_product_summary_skus():
        """Get summary of all products with their total quantities"""
        from ..models.product import Product
        
        # Use proper Product model relationships
        product_summaries = db.session.query(
            Product.id.label('product_id'),
            Product.name.label('product_name'),
            Product.base_unit.label('product_base_unit'),
            func.sum(ProductSKU.current_quantity).label('total_quantity'),
            func.count(ProductSKU.id).label('sku_count'),
            func.min(ProductSKU.low_stock_threshold).label('low_stock_threshold'),
            func.max(ProductSKU.updated_at).label('last_updated')
        ).join(ProductSKU).filter(
            ProductSKU.is_active == True,
            Product.is_active == True
        ).group_by(
            Product.id,
            Product.name,
            Product.base_unit
        ).all()

        products = []
        for summary in product_summaries:
            products.append({
                'product_id': summary.product_id,
                'product_name': summary.product_name,
                'product_base_unit': summary.product_base_unit,
                'total_quantity': float(summary.total_quantity or 0),
                'sku_count': summary.sku_count,
                'low_stock_threshold': float(summary.low_stock_threshold or 0),
                'last_updated': summary.last_updated
            })

        return products

    @staticmethod
    def get_or_create_sku(product_id, variant_id, size_label, sku_code=None):
        """Get existing SKU or create new one with automatic SKU generation"""
        from ..models.product import Product, ProductVariant
        from flask_login import current_user
        
        # Check if SKU already exists
        sku = ProductSKU.query.filter_by(
            product_id=product_id,
            variant_id=variant_id,
            size_label=size_label
        ).first()

        if sku:
            return sku

        # Get the product and variant
        product = Product.query.get(product_id)
        variant = ProductVariant.query.get(variant_id)
        
        if not product or not variant:
            raise ValueError("Product or variant not found")

        # Always generate SKU code automatically
        if not sku_code:
            sku_code = ProductService.generate_sku_code(product.name, variant.name, size_label)

        # Create new SKU
        sku = ProductSKU(
            product_id=product_id,
            variant_id=variant_id,
            size_label=size_label,
            unit=product.base_unit,  # Always inherit from parent product
            sku_code=sku_code,
            current_quantity=0.0,
            is_active=True,
            organization_id=current_user.organization_id if current_user.is_authenticated else None,
            created_by=current_user.id if current_user.is_authenticated else None
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

    