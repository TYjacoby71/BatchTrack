from flask import jsonify, render_template
from flask_login import login_required

from .. import drawers_bp, register_drawer_action


register_drawer_action(
    'units.quick_create',
    description='Create a custom unit inline before resuming the current task.',
    endpoint='drawers.units_quick_create_modal_get',
    success_event='units.quick_create.completed',
)


@drawers_bp.route('/units/quick-create-modal', methods=['GET'])
@login_required
def units_quick_create_modal_get():
    """Return the drawer that lets users create a custom unit."""
    modal_html = render_template('components/drawer/quick_create_unit_drawer.html')
    return jsonify({'success': True, 'modal_html': modal_html})
