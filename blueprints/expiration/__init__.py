
from flask import Blueprint

expiration_bp = Blueprint('expiration', __name__, template_folder='templates', static_folder='static')

from . import routes
