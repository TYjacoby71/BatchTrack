from flask import Blueprint

products_bp = Blueprint('products', __name__, template_folder='templates')

from . import product_routes
from . import product_api
from . import product_inventory
from . import product_variants
from .product_variants import *  
from .product_inventory import *
from .product_api import *
from .product_log_routes import *