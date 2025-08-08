from flask import Blueprint

quick_add_bp = Blueprint('quick_add', __name__, template_folder='templates')

# Import routes after blueprint creation to avoid circular imports
from . import routes