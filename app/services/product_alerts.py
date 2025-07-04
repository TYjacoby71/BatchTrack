from ..models import db, ProductSKU
from sqlalchemy import and_
from typing import List, Dict

class ProductAlertService:
    """Service for product-related alerts including low stock SKUs"""

    @staticmethod
    def get_low_stock_skus() -> List[ProductSKU]:
        """Get all ProductSKUs that are below their low stock threshold"""
        return ProductSKU.query.filter(
            and_(
                ProductSKU.low_stock_threshold > 0,
                ProductSKU.current_quantity <= ProductSKU.low_stock_threshold,
                ProductSKU.is_active == True
            )
        ).all()

    @staticmethod
    def get_out_of_stock_skus() -> List[ProductSKU]:
        """Get all ProductSKUs that are completely out of stock"""
        return ProductSKU.query.filter(
            and_(
                ProductSKU.current_quantity <= 0,
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