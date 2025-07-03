from flask import Blueprint

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Register API blueprint
from .product_api import product_api_bp
products_bp.register_blueprint(product_api_bp)