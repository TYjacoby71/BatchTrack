
from flask import Blueprint, request, jsonify
from flask_login import login_required
from services.unit_conversion import ConversionEngine
from models import InventoryItem

conversion_api_bp = Blueprint('conversion_api', __name__)

@conversion_api_bp.route('/check-convertible', methods=['POST'])
@login_required
def check_convertible():
    data = request.get_json()
    from_unit = data.get('from_unit')
    to_unit = data.get('to_unit')
    item_id = data.get('item_id')
    
    if not all([from_unit, to_unit, item_id]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        # Get item for density if needed
        item = InventoryItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        # Try to check convertibility
        convertible = ConversionEngine.can_convert(from_unit, to_unit, item.density)
        
        return jsonify({
            'convertible': convertible,
            'from_unit': from_unit,
            'to_unit': to_unit
        })
        
    except Exception as e:
        return jsonify({
            'convertible': False,
            'error': str(e)
        })
