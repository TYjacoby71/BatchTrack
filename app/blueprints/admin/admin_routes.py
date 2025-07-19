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
        from flask_login import current_user
        
        # Apply organization scoping
        query = InventoryItem.query.filter(InventoryItem.quantity <= 0)
        if current_user.is_authenticated and current_user.organization_id:
            query = query.filter(InventoryItem.organization_id == current_user.organization_id)
        elif current_user.user_type == 'developer':
            # Developers can clean up system-wide or selected org
            from flask import session
            selected_org_id = session.get('dev_selected_org_id')
            if selected_org_id:
                query = query.filter(InventoryItem.organization_id == selected_org_id)
        
        zero_rows = query.all()
        count = len(zero_rows)
        for row in zero_rows:
            db.session.delete(row)
        db.session.commit()
        flash(f'Successfully archived {count} zeroed inventory entries', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error archiving inventory: {str(e)}', 'error')
    return redirect(url_for('admin.cleanup_tools'))

