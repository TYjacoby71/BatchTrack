
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from .services import ExpirationService

expiration_bp = Blueprint('expiration', __name__)

@expiration_bp.route('/alerts')
@login_required
def alerts():
    """Main expiration alerts dashboard"""
    expired = ExpirationService.get_expired_inventory_items()
    expiring_soon = ExpirationService.get_expiring_soon_items(7)
    
    return render_template('expiration/alerts.html', 
                         expired=expired, 
                         expiring_soon=expiring_soon)

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
