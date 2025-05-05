
from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__, url_prefix='/fifo')

from . import routes
