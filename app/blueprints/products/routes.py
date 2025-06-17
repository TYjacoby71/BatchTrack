
from flask import Blueprint

products_bp = Blueprint('products', __name__, template_folder='templates')

# Import routes from the new modular structure
from ...routes.products import *
from ...routes.product_variants import *
from ...routes.product_inventory import *
from ...routes.product_api import *
