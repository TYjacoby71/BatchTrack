from flask import Blueprint

# Import all product-related blueprints
from .products import products_bp
from .api import products_api_bp
from .sku import sku_bp
from .product_inventory_routes import product_inventory_bp
from .product_variants import product_variants_bp

# Export all blueprints for external import
__all__ = ['products_bp', 'products_api_bp', 'sku_bp', 'product_inventory_bp', 'product_variants_bp']