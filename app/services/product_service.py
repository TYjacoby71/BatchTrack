from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory
from ..models.product import Product, ProductVariant
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from flask_login import current_user
import uuid

class ProductService:
    @staticmethod
    def generate_sku_code(product_name: str, variant_name: str, size_label: str):
        """Generate a unique SKU code"""
        return f"{product_name[:3].upper()}-{variant_name[:3].upper()}-{size_label[:3].upper()}-{str(uuid.uuid4())[:8].upper()}"
    @staticmethod
    def get_or_create_sku(product_name: str, variant_name: str = 'Base', size_label: str = 'Bulk', unit: str = 'g'):
        """Get or create a ProductSKU with proper Product/Variant relationships"""

        # Get or create Product
        product = Product.query.filter_by(
            name=product_name,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            product = Product(
                name=product_name,
                base_unit=unit,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(product)
            db.session.flush()

        # Get or create ProductVariant
        variant = ProductVariant.query.filter_by(
            product_id=product.id,
            name=variant_name
        ).first()

        if not variant:
            variant = ProductVariant(
                product_id=product.id,
                name=variant_name,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(variant)
            db.session.flush()

        # Get or create ProductSKU
        sku = ProductSKU.query.filter_by(
            product_id=product.id,
            variant_id=variant.id,
            size_label=size_label,
            organization_id=current_user.organization_id
        ).first()

        if not sku:
            # Generate SKU code
            sku_code = ProductService.generate_sku_code(product.name, variant.name, size_label)

            sku = ProductSKU(
                product_id=product.id,
                variant_id=variant.id,
                size_label=size_label,
                sku_code=sku_code,
                unit=unit,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(sku)
            db.session.flush()

        return sku

    @staticmethod
    def get_product_summary_skus():
        """Get summary of all products with their total quantities"""
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
            Product.is_active == True,
            Product.organization_id == current_user.organization_id
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
    def get_product_skus(product_id: int):
        """Get all SKUs for a specific product"""
        skus = ProductSKU.query.filter_by(
            product_id=product_id,
            organization_id=current_user.organization_id,
            is_active=True
        ).all()

        groups = []
        for sku in skus:
            groups.append({
                'sku_id': sku.id,
                'variant_name': sku.variant.name,
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
        return ProductSKU.query.join(Product).join(ProductVariant).filter(
            db.or_(
                Product.name.ilike(search_pattern),
                ProductVariant.name.ilike(search_pattern),
                ProductSKU.size_label.ilike(search_pattern),
                ProductSKU.sku_code.ilike(search_pattern)
            ),
            ProductSKU.is_active == True,
            ProductSKU.organization_id == current_user.organization_id
        ).order_by(
            Product.name,
            ProductVariant.name
        ).all()

    @staticmethod
    def get_products_summary():
        return ProductService.get_product_summary_skus()

    @staticmethod
    def get_low_stock_skus(threshold_multiplier: float = 1.0):
        """Get SKUs that are low on stock"""
        return ProductSKU.query.filter(
            ProductSKU.current_quantity <= ProductSKU.low_stock_threshold * threshold_multiplier,
            ProductSKU.is_active == True,
            ProductSKU.organization_id == current_user.organization_id
        ).all()
    @staticmethod
    def get_product_inventory_summary(product_id):
        """Get inventory summary for a product - all data derived from SKU level"""
        product = Product.query.get(product_id)
        if not product:
            return None

        active_skus = [sku for sku in product.skus if sku.is_active]
        total_inventory = sum(sku.current_quantity for sku in active_skus)
        low_stock_count = sum(1 for sku in active_skus if sku.is_low_stock)

        return {
            'product_id': product.id,
            'product_name': product.name,
            'total_inventory': total_inventory,
            'variant_count': product.variant_count,
            'low_stock_count': low_stock_count
        }