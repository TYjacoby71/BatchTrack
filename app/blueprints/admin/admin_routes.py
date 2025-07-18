from flask import Blueprint, redirect, url_for, request, flash, render_template
from flask_login import login_required
from ...models import db, User

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/units')
@login_required
def unit_manager():
    return redirect(url_for('conversion_bp.manage_units'))

@admin_bp.route('/admin/tools/cleanup')
@login_required
def cleanup_tools():
    return render_template('admin/cleanup_tools.html')

@admin_bp.route('/admin/tools/archive_zeroed', methods=['POST'])
@login_required
def archive_zeroed_inventory():
    """Archive all inventory entries with zero quantity"""
    try:
        from ...models import InventoryItem
        zero_rows = InventoryItem.query.filter(InventoryItem.quantity <= 0).all()
        count = len(zero_rows)
        for row in zero_rows:
            db.session.delete(row)
        db.session.commit()
        flash(f'Successfully archived {count} zeroed inventory entries', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error archiving inventory: {str(e)}', 'error')
    return redirect(url_for('admin.cleanup_tools'))

