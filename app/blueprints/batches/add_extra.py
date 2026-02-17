from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.utils.permissions import require_permission

from ...services.batch_service import BatchOperationsService

add_extra_bp = Blueprint("add_extra", __name__)


@add_extra_bp.route("/<int:batch_id>", methods=["POST"])
@login_required
@require_permission("batches.edit")
def add_extra_to_batch(batch_id):
    """Add extra items to batch - thin controller delegating to service"""
    try:
        data = request.get_json()
        extra_ingredients = data.get("extra_ingredients", [])
        extra_containers = data.get("extra_containers", [])
        extra_consumables = data.get("extra_consumables", [])

        # Delegate to service
        success, message, errors = BatchOperationsService.add_extra_items_to_batch(
            batch_id=batch_id,
            extra_ingredients=extra_ingredients,
            extra_containers=extra_containers,
            extra_consumables=extra_consumables,
        )

        if not success:
            return (
                jsonify({"status": "error", "message": message, "errors": errors}),
                400,
            )

        return jsonify({"status": "success", "message": message})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
