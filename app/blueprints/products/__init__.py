from flask import Blueprint

# Create the main products blueprint
products_bp = Blueprint('products', __name__, url_prefix='/products')

# Import the main products routes first
from . import routes
from . import product_api
from . import product_variants
from . import product_inventory_routes

# Register the product inventory blueprint
from .product_inventory_routes import product_inventory_bp
products_bp.register_blueprint(product_inventory_bp)