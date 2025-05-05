
from flask import render_template
from flask_login import login_required
from services.expiration_alerts import get_expired_inventory
from . import expiration_bp

@expiration_bp.route('/alerts')
@login_required
def alerts():
    expired = get_expired_inventory()
    return render_template('expiration_alerts.html', expired=expired)
