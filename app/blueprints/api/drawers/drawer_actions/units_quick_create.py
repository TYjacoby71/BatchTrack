"""Custom-unit quick-create drawer routes.

Synopsis:
Expose drawer endpoint for rendering the inline custom-unit creation modal
used when workflows require unit creation before continuing.

Glossary:
- Unit quick-create drawer: Modal for creating custom units in context.
- Drawer action registration: Metadata used by drawer orchestration clients.
- Success event: Frontend event emitted after drawer completion.
"""

from flask import jsonify, render_template
from flask_login import login_required

from app.utils.permissions import require_permission

from .. import drawers_bp, register_drawer_action

# --- Register drawer action ---
# Purpose: Publish custom-unit drawer metadata for frontend workflows.
# Inputs: Drawer key, endpoint, and success-event descriptors.
# Outputs: Drawer action registered for discovery.
register_drawer_action(
    "units.quick_create",
    description="Create a custom unit inline before resuming the current task.",
    endpoint="drawers.units_quick_create_modal_get",
    success_event="units.quick_create.completed",
)


# --- Render units quick-create drawer ---
# Purpose: Return the custom-unit creation drawer markup.
# Inputs: Authenticated request with inventory.edit permission.
# Outputs: JSON payload containing rendered modal HTML.
@drawers_bp.route("/units/quick-create-modal", methods=["GET"])
@login_required
@require_permission("inventory.edit")
def units_quick_create_modal_get():
    """Return the drawer that lets users create a custom unit."""
    modal_html = render_template("components/drawer/quick_create_unit_drawer.html")
    return jsonify({"success": True, "modal_html": modal_html})
