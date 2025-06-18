from flask import Blueprint

products_bp = Blueprint('products', __name__, template_folder='templates')

# Import all product-related routes
from .products import products_bp as main_products_bp
from .product_variants import product_variants_bp
from .product_inventory import product_inventory_bp  
from .product_api import product_api_bp
from .product_log_routes import product_log_bp

# Register sub-blueprints
def register_product_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(main_products_bp)
    app.register_blueprint(product_variants_bp)
    app.register_blueprint(product_inventory_bp)
    app.register_blueprint(product_api_bp)
    app.register_blueprint(product_log_bp)
