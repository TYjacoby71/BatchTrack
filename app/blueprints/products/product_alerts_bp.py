
from flask import Blueprint, render_template, url_for
from flask_login import login_required
from app.utils.permissions import require_permission

# Define the Blueprint
product_alerts_bp = Blueprint('product_alerts', __name__, url_prefix='/product-alerts')

@product_alerts_bp.route('/')
@login_required
@require_permission('alerts.view')
def product_alerts():
    return render_template('pages/products/alerts.html', breadcrumb_items=[{'label': 'Products', 'url': url_for('products.list_products')}, {'label': 'Alerts'}])
