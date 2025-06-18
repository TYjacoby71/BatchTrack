from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__, template_folder='templates')

from . import services

# Import routes if they exist
try:
    from . import routes
except ImportError:
    pass