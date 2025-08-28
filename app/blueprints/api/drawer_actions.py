
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models import db, InventoryItem
from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission

drawer_actions_bp = Blueprint('drawer_actions', __name__, url_prefix='/api/drawer-actions')

# ==================== CONVERSION ERRORS ====================

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['GET'])
@login_required
@require_permission('view_inventory')
def conversion_density_modal_get(ingredient_id):
    """Get density fix modal for ingredient"""
    ingredient = InventoryItem.query.filter_by(
        id=ingredient_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not ingredient:
        return jsonify({'error': 'Ingredient not found'}), 404

    try:
        modal_html = render_template('components/shared/density_fix_modal.html',
                                   ingredient=ingredient)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def conversion_density_modal_post(ingredient_id):
    """Update ingredient density"""
    ingredient = InventoryItem.query.filter_by(
        id=ingredient_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not ingredient:
        return jsonify({'error': 'Ingredient not found'}), 404

    try:
        data = request.get_json()
        density = float(data.get('density', 0))
        
        if density <= 0:
            return jsonify({'error': 'Density must be greater than 0'}), 400
        
        ingredient.density = density
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Density updated to {density} g/ml for {ingredient.name}'
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid density value'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update density: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/unit-mapping-modal', methods=['GET'])
@login_required
@require_permission('view_inventory')
def unit_mapping_modal():
    """Get unit mapping creation modal"""
    from_unit = request.args.get('from_unit', '')
    to_unit = request.args.get('to_unit', '')

    try:
        modal_html = render_template('components/shared/unit_mapping_fix_modal.html',
                                   from_unit=from_unit,
                                   to_unit=to_unit)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/unit-mapping-modal', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def create_unit_mapping():
    """Create custom unit mapping from modal"""
    from app.models import CustomUnitMapping
    
    try:
        data = request.get_json()
        from_unit = data.get('from_unit', '').strip()
        to_unit = data.get('to_unit', '').strip()
        conversion_factor = float(data.get('conversion_factor', 0))

        if not from_unit or not to_unit:
            return jsonify({'error': 'Both units are required'}), 400

        if conversion_factor <= 0:
            return jsonify({'error': 'Conversion factor must be greater than 0'}), 400

        # Check if mapping already exists
        existing = CustomUnitMapping.query.filter_by(
            from_unit=from_unit,
            to_unit=to_unit,
            organization_id=current_user.organization_id
        ).first()

        if existing:
            return jsonify({'error': 'Mapping already exists'}), 400

        # Create new mapping
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=conversion_factor,
            organization_id=current_user.organization_id
        )

        db.session.add(mapping)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Unit mapping created: {from_unit} → {to_unit}',
            'mapping': {
                'from_unit': from_unit,
                'to_unit': to_unit,
                'conversion_factor': conversion_factor
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create mapping: {str(e)}'}), 500

# ==================== GENERAL RETRY MECHANISM ====================

@drawer_actions_bp.route('/retry-operation', methods=['POST'])
@login_required
def retry_operation():
    """Generic retry mechanism for conversion operations"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        operation_data = data.get('operation_data', {})

        # Only handle conversion retries for now
        if operation_type == 'conversion':
            return retry_conversion_operation(operation_data)
        else:
            return jsonify({'error': 'Unknown operation type'}), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error_code': 'RETRY_FAILED',
            'message': f'Retry failed: {str(e)}'
        }), 500

def retry_conversion_operation(data):
    """Retry conversion after fixing underlying issue"""
    result = ConversionEngine.convert_units(
        amount=float(data.get('amount')),
        from_unit=data.get('from_unit'),
        to_unit=data.get('to_unit'),
        ingredient_id=data.get('ingredient_id')
    )
    return jsonify(result)
