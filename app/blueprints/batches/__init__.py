from flask import Blueprint

batches_bp = Blueprint('batches', __name__, template_folder='templates')

from . import routes

# Import individual batch operation blueprints
try:
    from .start_batch import start_batch_bp
except ImportError:
    start_batch_bp = None

try:
    from .finish_batch import finish_batch_bp
except ImportError:
    finish_batch_bp = None

try:
    from .cancel_batch import cancel_batch_bp
except ImportError:
    cancel_batch_bp = None

try:
    from .add_extra import add_extra_bp
except ImportError:
    add_extra_bp = None