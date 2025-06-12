
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import InventoryHistory, db
from datetime import datetime, timedelta
from . import expiration_bp

@expiration_bp.route('/alerts')
@login_required
def alerts():
    """Alias for expiration_alerts to support both URL patterns"""
    return expiration_alerts()

@expiration_bp.route('/expiration-alerts')
@login_required
def expiration_alerts():
    """Show expiration alerts"""
    # Get items expiring soon
    threshold_date = datetime.now() + timedelta(days=30)
    expiring_items = InventoryHistory.query.filter(
        InventoryHistory.expiration_date <= threshold_date,
        InventoryHistory.expiration_date >= datetime.now(),
        InventoryHistory.quantity > 0
    ).all()
    
    return render_template('expiration_alerts.html', expiring_items=expiring_items)

@expiration_bp.route('/update_expiration', methods=['POST'])
@login_required
def update_expiration():
    """Update expiration date for inventory item"""
    item_id = request.form.get('item_id')
    new_date = request.form.get('expiration_date')
    
    try:
        item = InventoryHistory.query.get_or_404(item_id)
        item.expiration_date = datetime.strptime(new_date, '%Y-%m-%d').date()
        db.session.commit()
        flash('Expiration date updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating expiration date: {str(e)}', 'error')
    
    return redirect(url_for('expiration.expiration_alerts'))
