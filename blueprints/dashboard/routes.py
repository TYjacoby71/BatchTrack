
from flask import Blueprint, render_template
from flask_login import login_required

dashboard_bp = Blueprint('user_dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')
