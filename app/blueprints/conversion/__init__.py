
from flask import Blueprint

conversion_bp = Blueprint('conversion_bp', __name__, url_prefix='/conversion')

from . import routes
