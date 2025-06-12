
from flask import Blueprint

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

from . import routes
