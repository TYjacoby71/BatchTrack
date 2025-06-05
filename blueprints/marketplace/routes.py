
from flask import Blueprint, render_template
from flask_login import login_required

marketplace_bp = Blueprint('marketplace', __name__)

@marketplace_bp.route('/')
@login_required
def index():
    """Marketplace integration management page"""
    return render_template('marketplace/index.html')
