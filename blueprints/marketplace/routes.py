from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/marketplace')

@marketplace_bp.route('/', endpoint='index')
@login_required
def index():
    return render_template('marketplace/index.html')

# API routes are in api/marketplace_routes.py