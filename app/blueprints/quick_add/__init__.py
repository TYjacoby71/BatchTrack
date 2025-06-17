
from flask import Blueprint

quick_add_bp = Blueprint('quick_add', __name__, template_folder='templates')

from . import routes
