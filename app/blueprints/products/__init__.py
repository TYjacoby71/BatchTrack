from flask import Blueprint

# Create the main products blueprint for web routes
products_bp = Blueprint('products', __name__, url_prefix='/products', template_folder='templates')

# Create separate API blueprint for all product APIs
products_api_bp = Blueprint('products_api', __name__, url_prefix='/api/products')

# Import web routes
from .products import *
from .product_variants import *
from .product_alerts import *
from .sku import *

# Import API routes - consolidate all APIs here
from .api import *

def register_product_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(products_bp)
    app.register_blueprint(products_api_bp)

# Make blueprints available for registration
__all__ = ['products_bp', 'products_api_bp', 'register_product_blueprints']