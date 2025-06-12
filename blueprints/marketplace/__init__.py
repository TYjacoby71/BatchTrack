
from flask import Blueprint

marketplace_bp = Blueprint('marketplace', __name__, template_folder='templates', static_folder='static')

from . import routes
