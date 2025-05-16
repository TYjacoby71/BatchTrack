
from flask import Blueprint

inventory_bp = Blueprint('inventory', __name__, 
                       template_folder='templates/inventory',
                       static_folder='static')

from . import routes
