from flask import Blueprint

# Import all product-related blueprints
from .products import products_bp
from .api import products_api_bp
from .sku import sku_bp
from .product_variants import product_variants_bp
from .product_inventory_routes import product_inventory_bp

def register_blueprints(app):
    app.register_blueprint(products_bp)
    app.register_blueprint(products_api_bp)
    app.register_blueprint(sku_bp)
    app.register_blueprint(product_variants_bp)
    app.register_blueprint(product_inventory_bp)

# Export all blueprints for external import
__all__ = ['products_bp', 'products_api_bp', 'product_inventory_bp', 'product_variants_bp', 'sku_bp', 'register_blueprints']