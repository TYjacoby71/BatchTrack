
from flask import Blueprint

expiration_bp = Blueprint('expiration', __name__, url_prefix='/expiration', template_folder='templates')

from . import routes, services
