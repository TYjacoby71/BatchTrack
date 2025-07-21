
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.services.unit_conversion import ConversionEngine
from app.utils.unit_utils import get_global_unit_list
from app.models.models import Unit

unit_api_bp = Blueprint('unit_api', __name__, url_prefix='/api')

@unit_api_bp.route('/units')
@login_required
def get_units():
    """Get available units for current user"""
    try:
        units = get_global_unit_list()
        
        return jsonify({
            'success': True,
            'data': [
                {
                    'id': unit.id,
                    'name': unit.name,
                    'symbol': unit.symbol,
                    'unit_type': unit.unit_type,
                    'base_unit': unit.is_base_unit
                } for unit in units
            ]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@unit_api_bp.route('/convert-units', methods=['POST'])
@login_required
def convert_units():
    """Convert between units"""
    try:
        data = request.get_json()
        from_unit_id = data.get('from_unit_id')
        to_unit_id = data.get('to_unit_id')
        quantity = data.get('quantity')
        ingredient_id = data.get('ingredient_id')
        
        if not all([from_unit_id, to_unit_id, quantity is not None]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
            
        from_unit = Unit.query.get(from_unit_id)
        to_unit = Unit.query.get(to_unit_id)
        
        if not from_unit or not to_unit:
            return jsonify({'success': False, 'error': 'Invalid unit ID'}), 400
            
        result = ConversionEngine.convert_units(
            quantity, from_unit.name, to_unit.name, ingredient_id
        )
        converted_quantity = result['converted_value']
        
        conversion_factor = converted_quantity / quantity if quantity != 0 else 0
        
        return jsonify({
            'success': True,
            'data': {
                'converted_quantity': converted_quantity,
                'from_unit': from_unit.symbol,
                'to_unit': to_unit.symbol,
                'conversion_factor': conversion_factor
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
