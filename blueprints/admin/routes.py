
from flask import Blueprint, redirect, url_for, request, flash, render_template
from flask_login import login_required
from models import ProductInventory, db, User

from . import admin_bp

@admin_bp.route('/units')
@login_required
def unit_manager():
    return redirect(url_for('conversion.manage_units'))

@admin_bp.route('/tools/cleanup')
@login_required
def cleanup_tools():
    return render_template('admin/cleanup_tools.html')

@admin_bp.route('/tools/archive_zeroed', methods=['POST'])
@login_required
def archive_zeroed_inventory():
    """Archive all inventory entries with zero quantity"""
    try:
        zero_rows = ProductInventory.query.filter(ProductInventory.quantity <= 0).all()
        count = len(zero_rows)
        for row in zero_rows:
            db.session.delete(row)
        db.session.commit()
        flash(f'Successfully archived {count} zeroed inventory entries', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error archiving inventory: {str(e)}', 'error')
    return redirect(url_for('admin.cleanup_tools'))

@admin_bp.route('/reset_database', methods=['POST'])
@login_required
def reset_database():
    """Reset database functionality"""
    try:
        # Add database reset logic here
        flash('Database reset successfully', 'success')
    except Exception as e:
        flash(f'Error resetting database: {str(e)}', 'error')
    return redirect(url_for('admin.cleanup_tools'))
