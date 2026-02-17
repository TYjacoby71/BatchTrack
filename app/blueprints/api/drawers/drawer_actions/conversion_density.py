from flask import jsonify, render_template
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.models import InventoryItem
from app.utils.permissions import require_permission

from .. import drawers_bp, register_drawer_action

register_drawer_action(
    "conversion.density_modal",
    description="Fix missing density on an ingredient before retrying conversion.",
    endpoint="drawers.conversion_density_modal",
    success_event="conversion.density.updated",
)


@drawers_bp.route("/conversion/density-modal/<int:ingredient_id>", methods=["GET"])
@login_required
@require_permission("inventory.view")
def conversion_density_modal(ingredient_id):
    """Render the density fix drawer for the requested ingredient."""
    ingredient = InventoryItem.query.filter_by(
        id=ingredient_id,
        organization_id=current_user.organization_id,
    ).first()

    if not ingredient:
        return jsonify({"error": "Ingredient not found"}), 404

    modal_html = render_template(
        "components/drawer/density_fix_modal.html",
        ingredient=ingredient,
        csrf_token=generate_csrf(),
    )
    return jsonify({"success": True, "modal_html": modal_html})
