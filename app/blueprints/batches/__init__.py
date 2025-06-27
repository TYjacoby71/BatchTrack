from flask import Blueprint

# Create the main batches blueprint
batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

# Import routes to register them with the blueprint
from . import routes
from .finish_batch import finish_batch_bp

# Import individual batch operation blueprints
try:
    from .start_batch import start_batch_bp
except ImportError:
    start_batch_bp = None

try:
    from .cancel_batch import cancel_batch_bp
except ImportError:
    cancel_batch_bp = None

try:
    from .add_extra import add_extra_bp
except ImportError:
    add_extra_bp = None