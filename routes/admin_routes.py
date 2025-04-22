from flask import Blueprint, redirect, url_for
from flask_login import login_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/units')
@login_required
def unit_manager():
    return redirect(url_for('conversion.manage_units'))