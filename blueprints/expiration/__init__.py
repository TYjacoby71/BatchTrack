from flask import Blueprint

expiration_bp = Blueprint('expiration', __name__, url_prefix='/expiration')

from . import routes