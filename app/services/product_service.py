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
            # Create inventory item for this SKU
            from ..models import InventoryItem
            inventory_item = InventoryItem(
                name=f"{product.name} - {variant.name} - {size_label}",
                type='product',  # Critical: mark as product type
                unit=unit,
                quantity=0.0,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()

            # Generate SKU code
            sku_code = ProductService.generate_sku_code(product.name, variant.name, size_label)

            # Generate SKU name - never leave it empty
            sku_name = f"{product.name} - {variant.name} - {size_label}"
            
            # Create the ProductSKU entry
            product_sku = ProductSKU(
                product_id=product.id,
                variant_id=variant.id,
                size_label=size_label,
                sku_code=sku_code,
                sku_name=sku_name,  # Always set the sku_name
                inventory_item_id=inventory_item.id,
                unit=unit,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )

            # Note: Perishable settings are managed at the inventory_item level
            # and should be set separately when needed (e.g., during batch completion)
            db.session.add(product_sku)
            db.session.flush()

        return sku

    @staticmethod
    def get_product_summary_skus():
        """Get summary of all products with their total quantities"""
        from ..models import InventoryItem

        product_summaries = db.session.query(
            Product.id.label('product_id'),
            Product.name.label('product_name'),
            Product.base_unit.label('product_base_unit'),
            func.sum(InventoryItem.quantity).label('total_quantity'),
            func.count(ProductSKU.inventory_item_id).label('sku_count'),
            func.min(ProductSKU.low_stock_threshold).label('low_stock_threshold'),
            func.max(ProductSKU.updated_at).label('last_updated')
        ).select_from(Product).join(
            ProductSKU, Product.id == ProductSKU.product_id
        ).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
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
                'sku_id': sku.inventory_item_id,
                'variant_name': sku.variant.name,
                'size_label': sku.size_label,
                'quantity': sku.inventory_item.quantity if sku.inventory_item else 0.0,
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
    def get_low_stock_skus(threshold_multiplier: float = 1.0):
        """Get SKUs that are low on stock"""
        from ..models import InventoryItem

        return ProductSKU.query.join(InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id).filter(
            InventoryItem.quantity <= ProductSKU.low_stock_threshold * threshold_multiplier,
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
        total_inventory = sum((sku.inventory_item.quantity if sku.inventory_item else 0.0) for sku in active_skus)
        low_stock_count = sum(1 for sku in active_skus if sku.is_low_stock)

        return {
            'product_id': product.id,
            'product_name': product.name,
            'total_inventory': total_inventory,
            'variant_count': product.variant_count,
            'low_stock_count': low_stock_count
        }

    @staticmethod
    def get_sku_by_id(sku_id):
        """Get a single SKU by ID with organization scoping"""
        return ProductSKU.query.filter_by(
            id=sku_id,
            organization_id=current_user.organization_id
        ).first()

    @staticmethod
    def get_all_products():
        """Get all active products for the current organization"""
        return Product.query.filter_by(
            is_active=True,
            organization_id=current_user.organization_id
        ).all()

    @staticmethod
    def get_product_variants(product_id):
        """Get all active variants for a specific product"""
        from ..models.product import Product, ProductVariant
        
        # First verify the product exists and belongs to the organization
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return None

        # Get active variants for this product
        return ProductVariant.query.filter_by(
            product_id=product.id,
            is_active=True
        ).all()

    @staticmethod
    def get_product_from_sku(sku_id):
        """Get Product ID from SKU ID with proper validation"""
        sku = ProductService.get_sku_by_id(sku_id)
        
        if not sku:
            return None
            
        if not sku.product_id:
            return None
            
        return {
            'product_id': sku.product_id,
            'sku_id': sku.id
        }

    @staticmethod
    def quick_add_product(product_name: str, variant_name: str = 'Base', product_base_unit: str = 'oz'):
        """Quick add product and variant, return structured response"""
        # Get or create the SKU with organization scoping
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name,
            size_label='Bulk',
            unit=product_base_unit
        )

        # Ensure the SKU belongs to the current user's organization
        if not sku.organization_id:
            sku.organization_id = current_user.organization_id

        db.session.commit()

        # Find the base product ID (first SKU for this product)
        base_sku = db.session.query(func.min(ProductSKU.id)).filter_by(
            product_name=sku.product.name,
            organization_id=current_user.organization_id
        ).scalar()

        return {
            'success': True,
            'product': {
                'id': base_sku,
                'name': sku.product.name,
                'product_base_unit': sku.unit
            },
            'variant': {
                'id': sku.id,
                'name': sku.variant.name
            }
        }