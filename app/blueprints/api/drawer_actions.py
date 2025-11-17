from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models import db, InventoryItem, IngredientCategory
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

        modal_html = render_template(
            'components/drawer/density_fix_modal.html',
            ingredient=ingredient
        )

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

# POST endpoint removed - using inventory edit route directly
# All density updates now go through the inventory edit route

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

# Removed product density modal routes; a single ingredient density modal remains

# ==================== INVENTORY QUICK-CREATE DRAWER ====================

@drawer_actions_bp.route('/inventory/quick-create-modal', methods=['GET'])
@login_required
def inventory_quick_create_modal_get():
    try:
        from app.utils.unit_utils import get_global_unit_list
        units = get_global_unit_list()
        categories = IngredientCategory.query.order_by(IngredientCategory.name.asc()).all()
        modal_html = render_template('components/drawer/quick_create_inventory_drawer.html',
                                     inventory_units=units,
                                     categories=categories)
        return jsonify({ 'success': True, 'modal_html': modal_html })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/units/quick-create-modal', methods=['GET'])
@login_required
def units_quick_create_modal_get():
    try:
        modal_html = render_template('components/drawer/quick_create_unit_drawer.html')
        return jsonify({ 'success': True, 'modal_html': modal_html })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to load modal: {str(e)}'}), 500


@drawer_actions_bp.route('/containers/unit-mismatch-modal', methods=['GET'])
@login_required
@require_permission('recipes.plan_production')
def container_unit_mismatch_modal():
    """Drawer to guide users through recipe/container unit mismatches."""
    recipe_id = request.args.get('recipe_id', type=int)
    requested_yield_unit = request.args.get('yield_unit')

    if not recipe_id:
        return jsonify({'success': False, 'error': 'Recipe ID required'}), 400

    recipe = Recipe.query.filter_by(
        id=recipe_id,
        organization_id=current_user.organization_id
    ).first()

    if not recipe:
        return jsonify({'success': False, 'error': 'Recipe not found'}), 404

    yield_unit = requested_yield_unit or recipe.predicted_yield_unit or 'count'

    container_items = []
    allowed_ids = getattr(recipe, 'allowed_containers', []) or []
    if allowed_ids:
        containers = InventoryItem.query.filter(
            InventoryItem.id.in_(allowed_ids),
            InventoryItem.organization_id == current_user.organization_id
        ).all()
        for container in containers:
            container_items.append({
                'name': container.container_display_name or container.name,
                'capacity': container.capacity,
                'capacity_unit': container.capacity_unit or 'count',
                'quantity': container.quantity or 0
            })

    modal_html = render_template(
        'components/drawer/container_unit_mismatch_drawer.html',
        recipe=recipe,
        yield_unit=yield_unit,
        container_items=container_items
    )

    return jsonify({'success': True, 'modal_html': modal_html})