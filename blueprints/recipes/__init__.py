
from flask import Blueprint

recipes_bp = Blueprint('recipes', __name__, url_prefix='/recipes')

from . import routes
