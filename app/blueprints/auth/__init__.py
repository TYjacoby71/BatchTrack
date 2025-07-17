from flask import Blueprint

auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Import routes to register them with the blueprint
from . import routes
from . import permissions