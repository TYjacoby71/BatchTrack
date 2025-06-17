from flask import Blueprint

api_bp = Blueprint('api', __name__)

from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp

def register_api_routes(app):
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(ingredient_api_bp)
    app.register_blueprint(container_api_bp)
    
    # Import and register fifo routes if they exist
    try:
        from .fifo_routes import fifo_api_bp
        app.register_blueprint(fifo_api_bp)
    except ImportError:
        pass

def init_api(app):
    register_api_routes(app)