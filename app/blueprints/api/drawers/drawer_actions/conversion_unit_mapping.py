"""Conversion unit-mapping drawer routes.

Synopsis:
Provide drawer endpoints for rendering and persisting organization-scoped
custom unit mappings required to complete blocked conversions.

Glossary:
- Unit-mapping drawer: Modal used to create/update conversion factors.
- Custom unit mapping: Organization-specific conversion relationship record.
- Mapping factor: Numeric multiplier translating from one unit to another.
"""

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import CustomUnitMapping, db
from app.utils.permissions import require_permission

from .. import drawers_bp, register_drawer_action

# --- Register drawer action ---
# Purpose: Advertise unit-mapping drawer metadata to drawer clients.
# Inputs: Drawer action key, endpoint, and success-event descriptors.
# Outputs: Drawer action registration in shared registry.
register_drawer_action(
    "conversion.unit_mapping_modal",
    description="Create a custom unit mapping required to finish a conversion.",
    endpoint="drawers.conversion_unit_mapping_modal_get",
    success_event="conversion.unit_mapping.created",
)


# --- Render unit-mapping drawer ---
# Purpose: Return modal HTML populated with source/target unit hints.
# Inputs: from_unit and to_unit query parameters.
# Outputs: JSON payload containing rendered modal HTML.
@drawers_bp.route("/conversion/unit-mapping-modal", methods=["GET"])
@login_required
@require_permission("inventory.view")
def conversion_unit_mapping_modal_get():
    """Return the unit mapping drawer contents."""
    from_unit = request.args.get("from_unit", "")
    to_unit = request.args.get("to_unit", "")

    modal_html = render_template(
        "components/shared/unit_mapping_fix_modal.html",
        from_unit=from_unit,
        to_unit=to_unit,
    )
    return jsonify({"success": True, "modal_html": modal_html})


# --- Persist unit mapping ---
# Purpose: Create or update custom conversion factor for scoped organization.
# Inputs: JSON body with from_unit, to_unit, and conversion_factor.
# Outputs: JSON success/error response after validation and commit attempt.
@drawers_bp.route("/conversion/unit-mapping-modal", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def conversion_unit_mapping_modal_post():
    """Create or update a unit mapping from the drawer."""
    data = request.get_json() or {}
    from_unit = data.get("from_unit")
    to_unit = data.get("to_unit")

    try:
        conversion_factor = float(data.get("conversion_factor", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Conversion factor must be numeric"}), 400

    if not from_unit or not to_unit:
        return jsonify({"error": "Both units are required"}), 400

    if conversion_factor <= 0:
        return jsonify({"error": "Conversion factor must be greater than 0"}), 400

    existing = CustomUnitMapping.scoped().filter_by(
        from_unit=from_unit,
        to_unit=to_unit,
        organization_id=current_user.organization_id,
    ).first()

    if existing:
        existing.conversion_factor = conversion_factor
        message = f"Updated unit mapping: {from_unit} → {to_unit} (factor: {conversion_factor})"
    else:
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=conversion_factor,
            organization_id=current_user.organization_id,
        )
        db.session.add(mapping)
        message = f"Created unit mapping: {from_unit} → {to_unit} (factor: {conversion_factor})"

    try:
        db.session.commit()
    except Exception as exc:  # pragma: no cover - defensive rollback
        db.session.rollback()
        return jsonify({"error": f"Failed to create mapping: {exc}"}), 500

    return jsonify({"success": True, "message": message})
