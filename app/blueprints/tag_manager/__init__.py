
from flask import Blueprint

tag_bp = Blueprint('tags', __name__, url_prefix='/tags')

from . import routes
