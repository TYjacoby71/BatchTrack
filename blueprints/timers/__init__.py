
from flask import Blueprint

timers_bp = Blueprint('timers', __name__, url_prefix='/timers', 
                     template_folder='templates')

from . import routes
