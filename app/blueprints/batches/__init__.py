from flask import Blueprint

batches_bp = Blueprint('batches', __name__, template_folder='templates')

from . import routes, start_batch, finish_batch, cancel_batch, add_extra