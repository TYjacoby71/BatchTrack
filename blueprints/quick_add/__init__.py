
from flask import Blueprint

quick_add_bp = Blueprint('quick_add', __name__, url_prefix='/quick-add')

from . import routes
