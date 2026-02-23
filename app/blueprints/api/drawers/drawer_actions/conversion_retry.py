"""Drawer-triggered conversion retry routes.

Synopsis:
Handle generic drawer retry submissions and re-run conversion operations after
users resolve missing prerequisites (such as density or unit mappings).

Glossary:
- Retry operation: Drawer-posted request to re-execute a failed action.
- Conversion operation: Unit-conversion attempt delegated to ConversionEngine.
- Operation payload: JSON structure containing retry type and operation data.
"""

from flask import jsonify, request
from flask_login import login_required

from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission

from .. import drawers_bp


# --- Retry operation router ---
# Purpose: Dispatch drawer retry requests to operation-specific handlers.
# Inputs: JSON payload with operation_type and operation_data.
# Outputs: JSON response from delegated retry handler or validation error.
@drawers_bp.route("/retry-operation", methods=["POST"])
@login_required
@require_permission("inventory.view")
def retry_operation():
    """Generic retry mechanism for conversion operations triggered by drawers."""
    data = request.get_json() or {}
    operation_type = data.get("operation_type")
    operation_data = data.get("operation_data", {})

    if operation_type == "conversion":
        return retry_conversion_operation(operation_data)

    return jsonify({"error": "Unknown operation type"}), 400


# --- Retry conversion operation ---
# Purpose: Re-run unit conversion after prerequisites are fixed.
# Inputs: Conversion payload with amount, units, and optional ingredient id.
# Outputs: JSON conversion result from ConversionEngine.
def retry_conversion_operation(data):
    """Retry conversion after fixing the underlying drawer issue."""
    result = ConversionEngine.convert_units(
        amount=float(data.get("amount", 0)),
        from_unit=data.get("from_unit"),
        to_unit=data.get("to_unit"),
        ingredient_id=data.get("ingredient_id"),
    )
    return jsonify(result)
