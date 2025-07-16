from flask import render_template, jsonify, request
from flask_login import login_required
from .services import ExpirationService
from . import expiration_bp

@expiration_bp.route('/alerts')
@login_required
def alerts():
    """Main expiration alerts dashboard"""
    from datetime import datetime
    expired = ExpirationService.get_expired_inventory_items()
    expiring_soon = ExpirationService.get_expiring_soon_items(7)

    return render_template('expiration/alerts.html', 
                         expired=expired, 
                         expiring_soon=expiring_soon,
                         today=datetime.now())

@expiration_bp.route('/api/expired-items')
@login_required
def api_expired_items():
    """API endpoint for expired items"""
    expired = ExpirationService.get_expired_inventory_items()
    return jsonify(expired)

@expiration_bp.route('/api/expiring-soon')
@login_required
def api_expiring_soon():
    """API endpoint for items expiring soon"""
    days_ahead = request.args.get('days', 7, type=int)
    expiring = ExpirationService.get_expiring_soon_items(days_ahead)
    return jsonify(expiring)

@expiration_bp.route('/api/summary')
@login_required
def api_summary():
    """API endpoint for expiration summary"""
    from ...services.combined_inventory_alerts import CombinedInventoryAlertService
    
    # Get user's expiration warning preference
    days_ahead = 7  # Default
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        from ...models.user_preferences import UserPreferences
        user_prefs = UserPreferences.get_for_user(current_user.id)
        if user_prefs:
            days_ahead = user_prefs.expiration_warning_days
    
    expiration_data = CombinedInventoryAlertService.get_expiration_alerts(days_ahead)
    
    return jsonify({
        'expired_total': expiration_data['expired_total'],
        'expiring_soon_total': expiration_data['expiring_soon_total']
    })

@expiration_bp.route('/api/calculate-expiration', methods=['POST'])
@login_required
def api_calculate_expiration():
    """Calculate expiration date from entry date and shelf life"""
    data = request.get_json()
    entry_date_str = data.get('entry_date')
    shelf_life_days = data.get('shelf_life_days')

    if not entry_date_str or not shelf_life_days:
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        from datetime import datetime
        entry_date = datetime.fromisoformat(entry_date_str.replace('Z', '+00:00'))
        expiration_date = ExpirationService.calculate_expiration_date(entry_date, shelf_life_days)

        return jsonify({
            'expiration_date': expiration_date.isoformat() if expiration_date else None,
            'days_until_expiration': ExpirationService.get_days_until_expiration(expiration_date)
        })
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400

@expiration_bp.route('/api/life-remaining/<int:fifo_id>')
@login_required
def api_life_remaining(fifo_id):
    """Get life remaining percentage for a FIFO entry"""
    from models import InventoryHistory

    entry = InventoryHistory.query.get_or_404(fifo_id)
    if not entry.expiration_date:
        return jsonify({'life_remaining_percent': None, 'non_perishable': True})

    percent = ExpirationService.get_life_remaining_percent(entry.timestamp, entry.expiration_date)
    days_until = ExpirationService.get_days_until_expiration(entry.expiration_date)

    return jsonify({
        'life_remaining_percent': round(percent, 1) if percent is not None else None,
        'days_until_expiration': days_until,
        'is_expired': days_until < 0 if days_until is not None else False
    })

@expiration_bp.route('/api/archive-expired', methods=['POST'])
@login_required
def api_archive_expired():
    """Archive expired items with zero quantity"""
    count = ExpirationService.archive_expired_items()
    return jsonify({'archived_count': count})

@expiration_bp.route('/api/mark-expired', methods=['POST'])
@login_required
def api_mark_expired():
    """Mark expired items as expired and remove from inventory"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        item_type = data.get('type')  # 'fifo' or 'product'
        item_id = data.get('id')

        print(f"Mark expired request - type: {item_type}, id: {item_id}")

        if not item_type or not item_id:
            return jsonify({'error': 'Missing type or id'}), 400

        if item_type not in ['fifo', 'product', 'raw']:
            return jsonify({'error': 'Invalid item type. Must be "fifo", "product", or "raw"'}), 400

        success, message = ExpirationService.mark_as_expired(item_type, item_id)
        
        if success:
            return jsonify({'success': True, 'message': message, 'expired_count': 1})
        else:
            return jsonify({'success': False, 'error': message, 'expired_count': 0}), 400
    except Exception as e:
        print(f"Error marking item as expired: {str(e)}")
        return jsonify({'error': str(e)}), 500

@expiration_bp.route('/api/summary')
@login_required
def api_expiration_summary():
    """Get expiration summary for dashboard widgets"""
    summary = ExpirationService.get_expiration_summary()
    return jsonify(summary)

@expiration_bp.route('/api/inventory-status/<int:inventory_item_id>')
@login_required
def api_inventory_status(inventory_item_id):
    """Get expiration status for a specific inventory item"""
    status = ExpirationService.get_inventory_item_expiration_status(inventory_item_id)
    return jsonify({
        'expired_count': len(status['expired_entries']),
        'expiring_soon_count': len(status['expiring_soon_entries']),
        'has_expiration_issues': status['has_expiration_issues']
    })

@expiration_bp.route('/api/product-status/<int:product_id>')
@login_required
def api_product_status(product_id):
    """Get expiration status for a specific product"""
    status = ExpirationService.get_product_expiration_status(product_id)
    return jsonify({
        'expired_count': len(status['expired_inventory']),
        'expiring_soon_count': len(status['expiring_soon_inventory']),
        'has_expiration_issues': status['has_expiration_issues']
    })

@expiration_bp.route('/api/product-inventory/<int:inventory_id>/expiration')
@login_required
def api_product_inventory_expiration(inventory_id):
    """Get calculated expiration date for specific product inventory"""
    expiration_date = ExpirationService.get_product_inventory_expiration_date(inventory_id)

    if not expiration_date:
        return jsonify({
            'expiration_date': None,
            'days_until_expiration': None,
            'is_expired': False,
            'is_perishable': False
        })

    days_until = ExpirationService.get_days_until_expiration(expiration_date)

    return jsonify({
        'expiration_date': expiration_date.isoformat(),
        'days_until_expiration': days_until,
        'is_expired': days_until < 0 if days_until is not None else False,
        'is_perishable': True
    })

@expiration_bp.route('/alerts')
@login_required
def expiration_alerts():
    """Display expiration alerts and management"""
    from ...models.user_preferences import UserPreferences
    from flask_login import current_user

    # Get user's expiration warning preference
    days_ahead = 7  # Default
    if current_user and current_user.is_authenticated:
        user_prefs = UserPreferences.get_for_user(current_user.id)
        if user_prefs:
            days_ahead = user_prefs.expiration_warning_days

    # Get comprehensive expiration data
    from ...services.combined_inventory_alerts import CombinedInventoryAlertService
    expiration_data = CombinedInventoryAlertService.get_expiration_alerts(days_ahead)
    
    # For template compatibility, structure the data
    expired_items = {
        'fifo_entries': expiration_data['expired_fifo_entries'],
        'product_inventory': expiration_data['expired_products']
    }
    expiring_soon = {
        'fifo_entries': expiration_data['expiring_fifo_entries'], 
        'product_inventory': expiration_data['expiring_products']
    }