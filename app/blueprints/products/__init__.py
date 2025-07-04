from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Import routes to register them
from . import products, sku, product_variants, product_inventory_routes, product_alerts
from .api import products_api_bp