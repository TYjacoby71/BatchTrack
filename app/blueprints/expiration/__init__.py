from flask import Blueprint

expiration_bp = Blueprint('expiration', __name__, template_folder='templates')

from . import routes