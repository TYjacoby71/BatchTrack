
from flask import Blueprint

inventory_bp = Blueprint('inventory', __name__, 
                       template_folder='templates/inventory',
                       static_folder='static',
                       url_prefix='/inventory')

from . import routes
