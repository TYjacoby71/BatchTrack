from flask import jsonify, render_template
from flask_login import login_required

from app.models import IngredientCategory
from app.utils.unit_utils import get_global_unit_list

from .. import drawers_bp, register_drawer_action


register_drawer_action(
    'inventory.quick_create',
    description='Quick-create an inventory item required by the current workflow.',
    endpoint='drawers.inventory_quick_create_modal_get',
    success_event='inventory.quick_create.completed',
)


@drawers_bp.route('/inventory/quick-create-modal', methods=['GET'])
@login_required
def inventory_quick_create_modal_get():
    """Return the quick-create inventory drawer."""
    units = get_global_unit_list()
    categories = IngredientCategory.query.order_by(IngredientCategory.name.asc()).all()
    modal_html = render_template(
        'components/drawer/quick_create_inventory_drawer.html',
        inventory_units=units,
        categories=categories,
    )
    return jsonify({'success': True, 'modal_html': modal_html})
