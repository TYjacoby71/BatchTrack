from flask import Blueprint

# Create the main products blueprint
products_bp = Blueprint('products', __name__, template_folder='templates')

# Import the main products routes first
from .products import *

# Import additional route modules to register them with the blueprint
from .product_variants import *  
from .product_api import *
from .product_log_routes import *

# Import the product_inventory blueprint separately
from .product_inventory import product_inventory_bp

# Make both blueprints available for registration
__all__ = ['products_bp', 'product_inventory_bp']