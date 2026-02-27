"""Inventory quick-create drawer routes.

Synopsis:
Expose drawer endpoint that returns inventory quick-create modal HTML with
unit lists and ingredient-category choices for inline workflow recovery.

Glossary:
- Quick-create drawer: Modal allowing lightweight inventory-item creation.
- Category list: Ingredient categories used to populate drawer form options.
- Drawer action registration: Metadata for drawer orchestration and events.
"""

from flask import jsonify, render_template
from flask_login import login_required

from app.models import IngredientCategory
from app.utils.permissions import require_permission
from app.utils.unit_utils import get_global_unit_list

from .. import drawers_bp, register_drawer_action

# --- Register drawer action ---
# Purpose: Publish inventory quick-create drawer metadata.
# Inputs: Drawer key, endpoint, description, and success event token.
# Outputs: Drawer action added to registry for client discovery.
register_drawer_action(
    "inventory.quick_create",
    description="Quick-create an inventory item required by the current workflow.",
    endpoint="drawers.inventory_quick_create_modal_get",
    success_event="inventory.quick_create.completed",
)


# --- Render inventory quick-create drawer ---
# Purpose: Build drawer HTML containing units and category options.
# Inputs: Authenticated request with inventory.edit permission.
# Outputs: JSON response containing rendered modal HTML.
@drawers_bp.route("/inventory/quick-create-modal", methods=["GET"])
@login_required
@require_permission("inventory.edit")
def inventory_quick_create_modal_get():
    """Return the quick-create inventory drawer."""
    units = get_global_unit_list()
    categories = IngredientCategory.scoped().order_by(IngredientCategory.name.asc()).all()
    modal_html = render_template(
        "components/drawer/quick_create_inventory_drawer.html",
        inventory_units=units,
        categories=categories,
    )
    return jsonify({"success": True, "modal_html": modal_html})
