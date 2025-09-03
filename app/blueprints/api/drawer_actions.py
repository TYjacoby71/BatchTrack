from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models import db, InventoryItem
from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission
from app.models.recipe import Recipe

drawer_actions_bp = Blueprint('drawer_actions', __name__, url_prefix='/api/drawer-actions')

# ==================== CONVERSION ERRORS ====================

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['GET'])
@login_required
@require_permission('inventory.view')
def conversion_density_modal_get(ingredient_id):
    """Get density fix modal for ingredient"""
    print(f"🔧 DENSITY MODAL: Looking for ingredient ID {ingredient_id} for org {current_user.organization_id}")

    ingredient = InventoryItem.query.filter_by(
        id=ingredient_id,
        organization_id=current_user.organization_id
    ).first()

    if not ingredient:
        print(f"🔧 DENSITY MODAL: Ingredient {ingredient_id} not found for org {current_user.organization_id}")
        return jsonify({'error': 'Ingredient not found'}), 404

    print(f"🔧 DENSITY MODAL: Found ingredient: {ingredient.name}, current density: {ingredient.density}")

    try:
        # Ensure CSRF token is available in modal
        from flask_wtf.csrf import generate_csrf
        csrf_token = generate_csrf()
        
        modal_html = render_template('components/shared/density_fix_modal.html',
                                   ingredient=ingredient, 
                                   csrf_token=csrf_token)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['POST'])
@login_required
@require_permission('inventory.edit')ry.edit')
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

@drawer_actions_bp.route('/api/drawer-actions/conversion/unit-mapping-modal', methods=['GET'])
@login_required
@require_permission('inventory.view')
def conversion_unit_mapping_modal_get():
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
@require_permission('inventory.edit')
def unit_mapping_modal_post():
    """Create unit mapping"""
    try:
        data = request.get_json()
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        conversion_factor = float(data.get('conversion_factor', 0))

        if not from_unit or not to_unit:
            return jsonify({'error': 'Both units are required'}), 400

        if conversion_factor <= 0:
            return jsonify({'error': 'Conversion factor must be greater than 0'}), 400

        # Import here to avoid circular imports
        from app.models import CustomUnitMapping

        # Check if mapping already exists
        existing = CustomUnitMapping.query.filter_by(
            from_unit=from_unit,
            to_unit=to_unit,
            organization_id=current_user.organization_id
        ).first()

        if existing:
            existing.conversion_factor = conversion_factor
            message = f'Updated unit mapping: {from_unit} → {to_unit} (factor: {conversion_factor})'
        else:
            mapping = CustomUnitMapping(
                from_unit=from_unit,
                to_unit=to_unit,
                conversion_factor=conversion_factor,
                organization_id=current_user.organization_id
            )
            db.session.add(mapping)
            message = f'Created unit mapping: {from_unit} → {to_unit} (factor: {conversion_factor})'

        db.session.commit()

        return jsonify({
            'success': True,
            'message': message
        })

    except ValueError:
        return jsonify({'error': 'Invalid conversion factor'}), 400
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


# ==================== CONTAINER PLANNING ERRORS ====================

@drawer_actions_bp.route('/containers/product-density-modal/<int:recipe_id>', methods=['GET'])
@login_required
@require_permission('recipes.plan_production')
def container_product_density_modal_get(recipe_id):
    """Render modal to capture product density for a recipe's container planning."""
    try:
        recipe = Recipe.query.filter_by(id=recipe_id, organization_id=current_user.organization_id).first()
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Reuse density modal with recipe context; template reads generically based on provided object
        modal_html = render_template('components/shared/product_density_fix_modal.html', recipe=recipe)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })
    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500


@drawer_actions_bp.route('/containers/product-density-modal/<int:recipe_id>', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def container_product_density_modal_post(recipe_id):
    """Accept product density input (session-scoped) and notify FE to retry auto-fill.

    We do not persist density on recipe; we simply echo back and FE will retry with provided value.
    """
    try:
        recipe = Recipe.query.filter_by(id=recipe_id, organization_id=current_user.organization_id).first()
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        data = request.get_json() or {}
        density = float(data.get('density', 0))
        if density <= 0:
            return jsonify({'error': 'Density must be greater than 0'}), 400

        # Return success; FE will dispatch productDensityUpdated and retry auto-fill
        return jsonify({
            'success': True,
            'message': f'Using product density {density} g/ml for {recipe.name}',
            'density': density
        })
    except ValueError:
        return jsonify({'error': 'Invalid density value'}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to accept density: {str(e)}'}), 500