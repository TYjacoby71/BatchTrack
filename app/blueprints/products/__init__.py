from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

from . import products, sku, product_variants, api, product_inventory_routes, reservation_routes, product_alerts
from .sku import sku_bp
from .reservation_routes import reservation_bp

def register_product_blueprints(app):
    app.register_blueprint(products_bp)
    app.register_blueprint(sku_bp, url_prefix='/products')
    app.register_blueprint(reservation_bp, url_prefix='/products')