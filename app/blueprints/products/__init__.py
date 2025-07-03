
from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Import route modules to register them with the blueprint
from . import products
from . import product_alerts
from . import product_variants
from . import product_inventory_routes
from . import product_log_routes
from . import product_api
