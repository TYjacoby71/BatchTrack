from flask import Blueprint, redirect, url_for
from flask_login import login_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/units')
@login_required
def unit_manager():
    return redirect(url_for('conversion_bp.manage_units'))
from models import ProductInventory, db
from flask import flash
from flask import render_template

@admin_bp.route('/admin/tools/cleanup')
@login_required
def cleanup_tools():
    return render_template('admin/cleanup_tools.html')

@admin_bp.route('/admin/tools/archive_zeroed', methods=['POST'])
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

from flask import request
from flask_wtf.csrf import generate_csrf

@admin_bp.route('/reset_database', methods=['POST'])
@login_required
def reset_database():
    if 'csrf_token' not in request.form:
        flash('Missing CSRF token', 'error')
        return redirect(url_for('admin.cleanup_tools'))
    """Reset the entire database to initial state"""
    try:
        # Drop all tables
        db.drop_all()
        # Recreate tables
        db.create_all()
        # Reseed initial data
        from seeders.unit_seeder import seed_units
        from seeders.ingredient_category_seeder import seed_categories
        seed_units()
        seed_categories()
        flash('Database has been reset successfully.')
    except Exception as e:
        flash(f'Error resetting database: {str(e)}', 'error')
    return redirect(url_for('admin.cleanup_tools'))