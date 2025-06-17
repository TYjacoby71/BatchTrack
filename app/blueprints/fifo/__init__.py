from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__, template_folder='templates')

from . import services