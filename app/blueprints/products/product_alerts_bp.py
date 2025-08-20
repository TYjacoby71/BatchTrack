
from flask import Blueprint, render_template
from flask_login import login_required

# Define the Blueprint
product_alerts_bp = Blueprint('product_alerts', __name__, url_prefix='/product-alerts')

@product_alerts_bp.route('/')
@login_required
def product_alerts():
    return render_template('pages/products/alerts.html')

# Define the register function that the blueprint registry expects
def register(app):
    """Register the product alerts blueprint with the Flask app."""
    app.register_blueprint(product_alerts_bp)
