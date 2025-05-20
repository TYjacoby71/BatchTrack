from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__)

from . import routes, services