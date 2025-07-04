from flask import Blueprint
from .products import products_bp
from .product_variants import product_variants_bp
from .product_inventory_routes import product_inventory_bp
from .sku import sku_bp

def register_products_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(product_variants_bp, url_prefix='/products')
    app.register_blueprint(product_inventory_bp, url_prefix='/products')
    app.register_blueprint(sku_bp, url_prefix='/products')