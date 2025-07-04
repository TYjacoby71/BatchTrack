from flask import Blueprint

# Import and register all product-related blueprints
from .products import products_bp
from .api import products_api_bp
from .sku import sku_bp
from .product_inventory_routes import product_inventory_bp
from .product_variants import product_variants_bp

def register_product_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(products_bp)
    app.register_blueprint(products_api_bp, url_prefix='/api/products')
    app.register_blueprint(sku_bp)
    app.register_blueprint(product_inventory_bp)
    app.register_blueprint(product_variants_bp, url_prefix='/products')