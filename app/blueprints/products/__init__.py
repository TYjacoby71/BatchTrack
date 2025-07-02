
from flask import Blueprint

# Create the main products blueprint
products_bp = Blueprint('products', __name__, template_folder='templates')

# Import the main products routes first
from .products import *

# Import additional route modules to register them with the blueprint
from .product_variants import *  
from .product_log_routes import *

# Import the new product_inventory blueprint (SKU-based)
from .product_inventory_routes import product_inventory_bp

# Import the product API blueprint
from .product_api import product_api_bp

# Make both blueprints available for registration
__all__ = ['products_bp', 'product_inventory_bp', 'product_api_bp']
