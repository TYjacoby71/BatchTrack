from flask import Blueprint

# Import the main products blueprint
from .products import products_bp
from .sku import sku_bp  
from .reservation_routes import reservations_bp

def register_product_blueprints(app):
    app.register_blueprint(products_bp)
    app.register_blueprint(sku_bp, url_prefix='/products')
    app.register_blueprint(reservations_bp, url_prefix='/products')