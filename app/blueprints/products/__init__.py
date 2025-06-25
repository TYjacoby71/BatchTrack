from flask import Blueprint

# Create the main products blueprint
products_bp = Blueprint('products', __name__, template_folder='templates')

# Import all route modules to register them with the blueprint
from .product_routes import *
from .product_variants import *  
from .product_inventory import *
from .product_api import *
from .product_log_routes import *