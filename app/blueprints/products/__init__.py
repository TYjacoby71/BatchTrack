from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

from . import routes
from . import products
from . import product_variants
from . import product_inventory_routes
from . import product_log_routes
from . import product_alerts
from .product_api import product_api_bp