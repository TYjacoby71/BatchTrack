from flask import Blueprint
from flask_login import login_required
from app.utils.permissions import require_permission

faults_bp = Blueprint('faults', __name__, url_prefix='/faults')

@faults_bp.route('/')
@login_required
@require_permission('alerts.view')
def view_fault_log():
    return "Fault log coming soon"