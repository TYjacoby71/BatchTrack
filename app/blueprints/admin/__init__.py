from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import admin_routes
from . import reservation_routes