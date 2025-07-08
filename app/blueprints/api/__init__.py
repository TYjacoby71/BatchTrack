from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import all route modules
from . import routes
from . import ingredient_routes
from . import stock_routes
from . import fifo_routes
from . import container_routes

def init_api(app):
    """Initialize API routes"""
    from .routes import api_bp
    from .ingredient_routes import ingredient_api_bp
    from .container_routes import container_api_bp
    from .fifo_routes import fifo_api_bp
    from .stock_routes import stock_api_bp
    from .shopify_routes import shopify_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ingredient_api_bp, url_prefix='/api/ingredients')
    app.register_blueprint(container_api_bp, url_prefix='/api/containers')
    app.register_blueprint(fifo_api_bp, url_prefix='/api/fifo')
    app.register_blueprint(stock_api_bp, url_prefix='/api/stock')
    app.register_blueprint(shopify_bp)