
from flask import Blueprint, render_template
from flask_login import login_required
from services.expiration_alerts import get_expired_inventory

expiration_bp = Blueprint('expiration', __name__)

@expiration_bp.route('/alerts')
@login_required
def alerts():
    expired = get_expired_inventory()
    return render_template('expiration_alerts.html', expired=expired)
