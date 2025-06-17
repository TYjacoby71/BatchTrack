from flask import Blueprint

timers_bp = Blueprint('timers', __name__, template_folder='templates')

from . import routes