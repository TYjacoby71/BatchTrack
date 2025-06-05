from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

marketplace = Blueprint('marketplace', __name__)

@marketplace.route('/', endpoint='index')
@login_required
def index():
    return render_template('marketplace/index.html')

# API routes are in api/marketplace_routes.py