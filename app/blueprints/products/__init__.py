from flask import Blueprint
from .products import products_bp
from .product_variants import product_variants_bp
from .product_inventory_routes import product_inventory_bp
from .sku import sku_bp
from .api import products_api_bp

def register_products_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(products_api_bp)
    app.register_blueprint(product_variants_bp, url_prefix='/products')
    app.register_blueprint(product_inventory_bp, url_prefix='/products')
    app.register_blueprint(sku_bp, url_prefix='/products')

# Export all blueprints for external import
__all__ = ['products_bp', 'products_api_bp', 'product_inventory_bp', 'product_variants_bp', 'sku_bp']