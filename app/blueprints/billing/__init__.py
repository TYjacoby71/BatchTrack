from flask import Blueprint

billing_bp = Blueprint('billing', __name__, template_folder='templates')

# Import routes to register them with the blueprint
from . import routes