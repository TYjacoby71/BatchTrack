
<old_str>
from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Register API blueprint
from .product_api import product_api_bp
products_bp.register_blueprint(product_api_bp)
</old_str>
<new_str>
from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Import route modules to register them with the blueprint
from . import products
from . import product_api  
from . import product_alerts
from . import product_variants
from . import product_inventory_routes
from . import product_log_routes
</new_str>
