
from flask import Blueprint

conversion_bp = Blueprint('conversion', __name__, template_folder='templates')

from . import routes
