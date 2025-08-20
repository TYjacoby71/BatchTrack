
from flask import Blueprint

product_alerts_bp = Blueprint('product_alerts', __name__, url_prefix='/product-alerts')

@product_alerts_bp.route('/')
def product_alerts():
    return "Product alerts coming soon"
