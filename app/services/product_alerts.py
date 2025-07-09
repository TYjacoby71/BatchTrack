from ..models import db, ProductSKU, InventoryItem
from sqlalchemy import and_
from typing import List, Dict
from flask_login import current_user

class ProductAlertService:
    """Service for product-related alerts including low stock SKUs"""

    @staticmethod
    def get_low_stock_skus():
        """Get all SKUs that are below their low stock threshold"""
        from ..models.models import InventoryItem

        return db.session.query(ProductSKU).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.quantity <= ProductSKU.low_stock_threshold,
                ProductSKU.low_stock_threshold > 0,
                ProductSKU.is_active == True
            )
        ).all()

    @staticmethod
    def get_out_of_stock_skus():
        """Get all SKUs that are out of stock"""
        from ..models.models import InventoryItem

        return db.session.query(ProductSKU).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.quantity == 0,
                ProductSKU.is_active == True
            )
        ).all()

    @staticmethod
    def get_product_stock_summary() -> Dict:
        """Get summary of product stock issues"""
        low_stock_skus = ProductAlertService.get_low_stock_skus()
        out_of_stock_skus = ProductAlertService.get_out_of_stock_skus()

        # Group by product name to avoid duplicates
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
            'low_stock_skus': low_stock_skus,
            'out_of_stock_skus': out_of_stock_skus,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'low_stock_count': len(low_stock_skus),
            'out_of_stock_count': len(out_of_stock_skus),
            'affected_products_count': len(set(low_stock_products.keys()) | set(out_of_stock_products.keys()))
        }