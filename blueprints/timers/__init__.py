from flask import Blueprint

timers_bp = Blueprint('timers', __name__, url_prefix='/timers')

from . import routes