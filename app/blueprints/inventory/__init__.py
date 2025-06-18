from flask import Blueprint

inventory_bp = Blueprint('inventory', __name__, template_folder='templates')

# Import routes to register them with the blueprint
from .routes import *