from flask import Blueprint

# Main products blueprint - this will be the container
products_bp = Blueprint('products_main', __name__, template_folder='templates')

# Register sub-blueprints
def register_product_blueprints(app):
    """Register all product-related blueprints"""
    try:
        from .products import products_bp as main_products_bp
        app.register_blueprint(main_products_bp)
    except ImportError:
        pass
    
    try:
        from .product_variants import product_variants_bp
        app.register_blueprint(product_variants_bp)
    except ImportError:
        pass
    
    try:
        from .product_inventory import product_inventory_bp  
        app.register_blueprint(product_inventory_bp)
    except ImportError:
        pass
    
    try:
        from .product_api import product_api_bp
        app.register_blueprint(product_api_bp)
    except ImportError:
        pass
    
    try:
        from .product_log_routes import product_log_bp
        app.register_blueprint(product_log_bp)
    except ImportError:
        pass
