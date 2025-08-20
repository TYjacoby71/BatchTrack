from flask import Blueprint

faults_bp = Blueprint('faults', __name__, url_prefix='/faults')

@faults_bp.route('/')
def view_fault_log():
    return "Fault log coming soon"