"""Unit API routes for list/search/conversion operations.

Synopsis:
Expose authenticated endpoints that provide available units, unit typeahead
search, and unit-to-unit conversion through the conversion engine.

Glossary:
- Unit catalog: Active unit definitions used by inventory and forms.
- Unit search: Filtered subset of units by type and free-text query.
- Conversion engine: Service that performs quantity/unit transformations.
"""
import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models.models import Unit
from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission
from app.utils.unit_utils import get_global_unit_list

logger = logging.getLogger(__name__)


# --- Unit API blueprint ---
# Purpose: Group unit-related API routes under /api.
# Inputs: None.
# Outputs: Blueprint namespace for unit endpoints.
unit_api_bp = Blueprint("unit_api", __name__, url_prefix="/api")


# --- Get units ---
# Purpose: Return available units for authenticated users.
# Inputs: None.
# Outputs: JSON payload containing unit metadata list.
@unit_api_bp.route("/units")
@login_required
@require_permission("inventory.view")
def get_units():
    """Get available units for current user"""
    try:
        units = get_global_unit_list()

        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "id": unit.id,
                        "name": unit.name,
                        "symbol": unit.symbol,
                        "unit_type": unit.unit_type,
                        "base_unit": unit.is_base_unit,
                    }
                    for unit in units
                ],
            }
        )

    except Exception as e:
        logger.warning("Suppressed exception fallback at app/blueprints/api/unit_routes.py:56", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# --- Search units ---
# Purpose: Return units filtered by type and optional query text.
# Inputs: Query params type/unit_type and q.
# Outputs: JSON payload with up to 25 matching unit records.
@unit_api_bp.route("/unit-search")
@login_required
@require_permission("inventory.view")
def unit_search():
    """Search units by type and optional query, scoped to org for custom units.

    Query params:
      - type: unit_type to filter (e.g., 'count')
      - q: substring match on name (optional)
    """
    try:
        unit_type = (
            request.args.get("type") or request.args.get("unit_type") or ""
        ).strip()
        q = (request.args.get("q") or "").strip()

        # Reuse the same source of truth as other unit lists
        units = get_global_unit_list() or []

        # Filter by type if provided
        if unit_type:
            units = [u for u in units if (getattr(u, "unit_type", None) == unit_type)]

        # Filter by query (case-insensitive substring on name)
        if q:
            q_lower = q.lower()
            units = [
                u
                for u in units
                if (getattr(u, "name", "") or "").lower().find(q_lower) != -1
            ]

        # Sort like other lists
        units.sort(
            key=lambda u: (
                str(getattr(u, "unit_type", "") or ""),
                str(getattr(u, "name", "") or ""),
            )
        )

        results = units[:25]
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "id": getattr(u, "id", None),
                        "name": getattr(u, "name", ""),
                        "unit_type": getattr(u, "unit_type", None),
                        "symbol": getattr(u, "symbol", None),
                        "is_custom": getattr(u, "is_custom", False),
                    }
                    for u in results
                ],
            }
        )
    except Exception as e:
        logger.warning("Suppressed exception fallback at app/blueprints/api/unit_routes.py:120", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# --- Convert units ---
# Purpose: Convert quantity between two unit ids through conversion service.
# Inputs: JSON payload with from_unit_id, to_unit_id, quantity, ingredient_id.
# Outputs: JSON payload with converted quantity and conversion factor.
@unit_api_bp.route("/convert-units", methods=["POST"])
@login_required
@require_permission("inventory.view")
def convert_units():
    """Convert between units"""
    try:
        data = request.get_json()
        from_unit_id = data.get("from_unit_id")
        to_unit_id = data.get("to_unit_id")
        quantity = data.get("quantity")
        ingredient_id = data.get("ingredient_id")

        if not all([from_unit_id, to_unit_id, quantity is not None]):
            return (
                jsonify({"success": False, "error": "Missing required parameters"}),
                400,
            )

        from app.extensions import db

        from_unit = db.session.get(Unit, from_unit_id)
        to_unit = db.session.get(Unit, to_unit_id)

        if not from_unit or not to_unit:
            return jsonify({"success": False, "error": "Invalid unit ID"}), 400

        result = ConversionEngine.convert_units(
            quantity, from_unit.name, to_unit.name, ingredient_id
        )
        converted_quantity = result["converted_value"]

        conversion_factor = converted_quantity / quantity if quantity != 0 else 0

        return jsonify(
            {
                "success": True,
                "data": {
                    "converted_quantity": converted_quantity,
                    "from_unit": from_unit.symbol,
                    "to_unit": to_unit.symbol,
                    "conversion_factor": conversion_factor,
                },
            }
        )

    except Exception as e:
        logger.warning("Suppressed exception fallback at app/blueprints/api/unit_routes.py:173", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
