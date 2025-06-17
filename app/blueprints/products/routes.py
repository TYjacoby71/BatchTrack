
from flask import Blueprint

products_bp = Blueprint('products', __name__, template_folder='templates')

# Import routes from the new modular structure
try:
    from ...routes.products import *
except ImportError:
    pass

try:
    from ...routes.product_variants import *
except ImportError:
    pass

try:
    from ...routes.product_inventory import *
except ImportError:
    pass

try:
    from ...routes.product_api import *
except ImportError:
    pass
