from flask import Blueprint

batches_bp = Blueprint('batches', __name__, template_folder='templates')

# Import routes to register them
from . import routes, start_batch, finish_batch, cancel_batch, add_extra