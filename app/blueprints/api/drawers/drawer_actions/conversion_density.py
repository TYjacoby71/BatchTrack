"""Conversion density-fix drawer routes.

Synopsis:
Expose the drawer endpoint that renders density-fix UI for ingredients when a
unit conversion requires density metadata before retry.

Glossary:
- Density-fix drawer: Modal prompting users to supply missing density values.
- Ingredient scope: Organization-filtered inventory item lookup.
- Drawer action registration: Metadata linking drawer keys to endpoints/events.
"""

from flask import jsonify, render_template
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.models import InventoryItem
from app.utils.permissions import require_permission

from .. import drawers_bp, register_drawer_action

# --- Register drawer action ---
# Purpose: Publish conversion-density drawer metadata for frontend orchestration.
# Inputs: Drawer action key, endpoint name, and success event token.
# Outputs: Drawer action registration in the shared drawer registry.
register_drawer_action(
    "conversion.density_modal",
    description="Fix missing density on an ingredient before retrying conversion.",
    endpoint="drawers.conversion_density_modal",
    success_event="conversion.density.updated",
)


# --- Render conversion density drawer ---
# Purpose: Return density-fix drawer HTML for a scoped ingredient.
# Inputs: Ingredient id path parameter from conversion retry flow.
# Outputs: JSON response with rendered modal HTML or not-found error.
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
