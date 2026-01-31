from flask import Blueprint

# Import all the blueprints
from .products import products_bp
from .product_inventory_routes import product_inventory_bp
from .reservation_routes import reservation_bp, reservations_bp
from .sku import sku_bp
from .product_variants import product_variants_bp
from .product_alerts_bp import product_alerts_bp
from .api import products_api_bp

def register_product_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(products_bp)
    app.register_blueprint(product_inventory_bp)
    app.register_blueprint(reservation_bp)
    app.register_blueprint(sku_bp)
    app.register_blueprint(product_variants_bp)
    app.register_blueprint(product_alerts_bp)
    app.register_blueprint(products_api_bp)