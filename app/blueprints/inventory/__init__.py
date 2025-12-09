
from flask import Blueprint

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

# Import routes to register them with the blueprint
from . import routes
