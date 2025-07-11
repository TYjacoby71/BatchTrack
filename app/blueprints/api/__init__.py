from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from . import routes
from . import container_routes
from . import ingredient_routes  
from . import stock_routes
from . import fifo_routes
from . import reservation_routes

# Register the container routes with the main API blueprint
api_bp.register_blueprint(container_routes.container_api_bp)
api_bp.register_blueprint(ingredient_routes.ingredient_api_bp)
api_bp.register_blueprint(stock_routes.stock_api_bp)