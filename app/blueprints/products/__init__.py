from flask import Blueprint

products_bp = Blueprint('products', __name__)

from . import products, sku, product_variants, product_inventory_routes, product_alerts, api

# Register API sub-blueprint
from .api import products_api_bp
products_bp.register_blueprint(products_api_bp)