
from ..models import db, InventoryItem, ProductSKU
from sqlalchemy import and_
from typing import List, Dict
from flask_login import current_user

class CombinedInventoryAlertService:
    """Unified service for all inventory alerts - raw materials and products"""

    @staticmethod
    def get_low_stock_ingredients():
        """Get all raw ingredients/containers that are below their low stock threshold"""
        from flask_login import current_user
        query = InventoryItem.query.filter(
            and_(
                InventoryItem.low_stock_threshold > 0,
                InventoryItem.quantity <= InventoryItem.low_stock_threshold,
                ~InventoryItem.type.in_(['product', 'product-reserved'])
            )
        )
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(InventoryItem.organization_id == current_user.organization_id)
        return query.all()

    @staticmethod
    def get_low_stock_skus():
        """Get all product SKUs that are below their low stock threshold"""
        from flask_login import current_user
        query = db.session.query(ProductSKU).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.quantity <= ProductSKU.low_stock_threshold,
                ProductSKU.low_stock_threshold > 0,
                ProductSKU.is_active == True
            )
        )
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(ProductSKU.organization_id == current_user.organization_id)
        return query.all()

    @staticmethod
    def get_out_of_stock_skus():
        """Get all product SKUs that are out of stock"""
        from flask_login import current_user
        query = db.session.query(ProductSKU).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.quantity == 0,
                ProductSKU.is_active == True
            )
        )
        if current_user and current_user.is_authenticated and current_user.organization_id:
            query = query.filter(ProductSKU.organization_id == current_user.organization_id)
        return query.all()

    @staticmethod
    def get_unified_stock_summary() -> Dict:
        """Get comprehensive summary of all inventory stock issues"""
        # Get raw material alerts
        low_stock_ingredients = CombinedInventoryAlertService.get_low_stock_ingredients()
        
        # Get product alerts
        low_stock_skus = CombinedInventoryAlertService.get_low_stock_skus()
        out_of_stock_skus = CombinedInventoryAlertService.get_out_of_stock_skus()

        # Group products by name to avoid duplicates
        low_stock_products = {}
        out_of_stock_products = {}

        for sku in low_stock_skus:
            if sku.product.name not in low_stock_products:
                low_stock_products[sku.product.name] = []
            low_stock_products[sku.product.name].append(sku)

        for sku in out_of_stock_skus:
            if sku.product.name not in out_of_stock_products:
                out_of_stock_products[sku.product.name] = []
            out_of_stock_products[sku.product.name].append(sku)

        return {
            # Raw materials
            'low_stock_ingredients': low_stock_ingredients,
            'low_stock_ingredients_count': len(low_stock_ingredients),
            
            # Products
            'low_stock_skus': low_stock_skus,
            'out_of_stock_skus': out_of_stock_skus,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'low_stock_count': len(low_stock_skus),
            'out_of_stock_count': len(out_of_stock_skus),
            'affected_products_count': len(set(low_stock_products.keys()) | set(out_of_stock_products.keys())),
            
            # Combined totals
            'total_low_stock_items': len(low_stock_ingredients) + len(low_stock_skus),
            'total_critical_items': len(out_of_stock_skus),
            'has_any_alerts': len(low_stock_ingredients) > 0 or len(low_stock_skus) > 0 or len(out_of_stock_skus) > 0
        }

    @staticmethod
    def get_product_stock_summary() -> Dict:
        """Backward compatibility method for product-specific alerts"""
        unified_summary = CombinedInventoryAlertService.get_unified_stock_summary()
        
        # Return only product-related data for compatibility
        return {
            'low_stock_skus': unified_summary['low_stock_skus'],
            'out_of_stock_skus': unified_summary['out_of_stock_skus'],
            'low_stock_products': unified_summary['low_stock_products'],
            'out_of_stock_products': unified_summary['out_of_stock_products'],
            'low_stock_count': unified_summary['low_stock_count'],
            'out_of_stock_count': unified_summary['out_of_stock_count'],
            'affected_products_count': unified_summary['affected_products_count']
        }
