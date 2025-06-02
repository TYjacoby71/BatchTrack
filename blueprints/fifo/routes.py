
from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__, url_prefix='/fifo')

# FIFO functionality has been moved to the inventory view with filter toggle
