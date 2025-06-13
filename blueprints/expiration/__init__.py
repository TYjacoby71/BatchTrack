
from flask import Blueprint
import os

# Get the directory where this __init__.py file is located
blueprint_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(blueprint_dir, 'templates')

expiration_bp = Blueprint('expiration', __name__, url_prefix='/expiration', template_folder=template_dir)

from . import routes, services
