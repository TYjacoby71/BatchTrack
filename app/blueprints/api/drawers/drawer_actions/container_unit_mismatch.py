from flask import jsonify, render_template, request
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from app.models import InventoryItem, Recipe, db
from app.utils.permissions import require_permission
from app.utils.unit_utils import get_global_unit_list

from .. import drawers_bp, register_drawer_action


register_drawer_action(
    'containers.unit_mismatch',
    description='Resolve yield/container unit mismatches for production planning.',
    endpoint='drawers.container_unit_mismatch_modal',
    success_event='container.plan.updated',
)


@drawers_bp.route('/containers/unit-mismatch-modal', methods=['GET'])
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
        organization_id=current_user.organization_id,
    ).first()

    if not recipe:
        return jsonify({'success': False, 'error': 'Recipe not found'}), 404

    yield_unit = requested_yield_unit or recipe.predicted_yield_unit or 'count'

    container_items = []
    allowed_ids = getattr(recipe, 'allowed_containers', []) or []
    if allowed_ids:
        containers = InventoryItem.query.filter(
            InventoryItem.id.in_(allowed_ids),
            InventoryItem.organization_id == current_user.organization_id,
        ).all()
        for container in containers:
            container_items.append(
                {
                    'name': container.container_display_name or container.name,
                    'capacity': container.capacity,
                    'capacity_unit': container.capacity_unit or 'count',
                    'quantity': container.quantity or 0,
                }
            )

    modal_html = render_template(
        'components/drawer/container_unit_mismatch_drawer.html',
        recipe=recipe,
        yield_unit=yield_unit,
        container_items=container_items,
        unit_options=get_global_unit_list(),
    )

    return jsonify({'success': True, 'modal_html': modal_html})


@drawers_bp.route('/containers/unit-mismatch-modal/<int:recipe_id>/yield', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def container_unit_mismatch_update_yield(recipe_id):
    """Quickly update a recipe's predicted yield and unit from the drawer."""
    recipe = Recipe.query.filter_by(
        id=recipe_id,
        organization_id=current_user.organization_id,
    ).first()

    if not recipe:
        return jsonify({'success': False, 'error': 'Recipe not found'}), 404

    data = request.get_json() or request.form
    try:
        validate_csrf(data.get('csrf_token'))
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 400

    try:
        new_yield = float(data.get('predicted_yield', recipe.predicted_yield or 0) or 0)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid yield amount'}), 400

    new_unit = (data.get('predicted_yield_unit') or '').strip()
    if not new_unit:
        return jsonify({'success': False, 'error': 'Yield unit is required'}), 400

    recipe.predicted_yield = new_yield
    recipe.predicted_yield_unit = new_unit

    try:
        db.session.commit()
    except Exception as exc:  # pragma: no cover - rollback guard
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Failed to update recipe: {exc}'}), 500

    return jsonify({'success': True, 'yield_amount': new_yield, 'yield_unit': new_unit})
