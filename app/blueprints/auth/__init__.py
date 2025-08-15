from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import routes
from .permissions import manage_permissions, toggle_permission_status

# Add permission routes
auth_bp.add_url_rule('/permissions', 'manage_permissions', manage_permissions, methods=['GET'])
auth_bp.add_url_rule('/permissions/toggle', 'toggle_permission_status', toggle_permission_status, methods=['POST'])