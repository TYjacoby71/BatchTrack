from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from . import routes
from . import container_routes
from . import ingredient_routes  
from . import stock_routes
from . import fifo_routes
from . import reservation_routes