from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import all route modules to register them
from . import routes
from . import ingredient_routes
from . import stock_routes
from . import fifo_routes
from . import reservation_routes
from . import container_routes

# Register sub-blueprints
from .ingredient_routes import ingredient_api_bp
from .stock_routes import stock_api_bp
from .container_routes import container_api_bp
from .fifo_routes import fifo_api_bp
from .reservation_routes import reservation_api_bp

api_bp.register_blueprint(ingredient_api_bp)
api_bp.register_blueprint(stock_api_bp)
api_bp.register_blueprint(container_api_bp)
api_bp.register_blueprint(fifo_api_bp)
api_bp.register_blueprint(reservation_api_bp)