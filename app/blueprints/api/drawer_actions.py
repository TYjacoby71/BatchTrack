
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models import db, InventoryItem, Unit, CustomUnitMapping, IngredientCategory
from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission

drawer_actions_bp = Blueprint('drawer_actions', __name__, url_prefix='/api/drawer-actions')


@drawer_actions_bp.route('/density-modal/<int:ingredient_id>', methods=['GET'])
@login_required
@require_permission('view_inventory')
def get_density_modal(ingredient_id):
    """Get density modal for missing density error"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)
    
    # Check organization access
    if ingredient.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get category default density if available
    suggested_density = None
    if ingredient.category and ingredient.category.default_density:
        suggested_density = ingredient.category.default_density
    
    modal_html = render_template('components/shared/density_fix_modal.html',
                               ingredient=ingredient,
                               suggested_density=suggested_density)
    
    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'ingredient_id': ingredient_id,
        'ingredient_name': ingredient.name,
        'current_density': ingredient.density,
        'suggested_density': suggested_density
    })


@drawer_actions_bp.route('/update-density/<int:ingredient_id>', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def update_density(ingredient_id):
    """Update ingredient density from modal"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)
    
    # Check organization access
    if ingredient.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        new_density = float(data.get('density', 0))
        
        if new_density <= 0:
            return jsonify({'error': 'Density must be greater than 0'}), 400
        
        ingredient.density = new_density
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Density updated for {ingredient.name}',
            'new_density': new_density
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid density value'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update density: {str(e)}'}), 500


@drawer_actions_bp.route('/unit-mapping-modal', methods=['GET'])
@login_required
@require_permission('view_conversion')
def get_unit_mapping_modal():
    """Get unit mapping modal for missing custom mapping error"""
    from_unit = request.args.get('from_unit')
    to_unit = request.args.get('to_unit')
    
    # Get all units for dropdown
    units = Unit.query.filter_by(is_active=True).order_by(Unit.name).all()
    
    modal_html = render_template('components/shared/unit_mapping_fix_modal.html',
                               from_unit=from_unit,
                               to_unit=to_unit,
                               units=units)
    
    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'from_unit': from_unit,
        'to_unit': to_unit
    })


@drawer_actions_bp.route('/create-unit-mapping', methods=['POST'])
@login_required
@require_permission('edit_conversion')
def create_unit_mapping():
    """Create custom unit mapping from modal"""
    try:
        data = request.get_json()
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        conversion_factor = float(data.get('conversion_factor', 1))
        
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
        
        # Create mapping
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=conversion_factor,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        
        db.session.add(mapping)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Custom mapping created: 1 {from_unit} = {conversion_factor} {to_unit}'
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid conversion factor'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create mapping: {str(e)}'}), 500


@drawer_actions_bp.route('/retry-conversion', methods=['POST'])
@login_required
def retry_conversion():
    """Retry conversion after fixing the underlying issue"""
    try:
        data = request.get_json()
        amount = float(data.get('amount'))
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        ingredient_id = data.get('ingredient_id')
        
        result = ConversionEngine.convert_units(
            amount=amount,
            from_unit=from_unit,
            to_unit=to_unit,
            ingredient_id=ingredient_id
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error_code': 'SYSTEM_ERROR',
            'message': f'Retry failed: {str(e)}'
        }), 500
