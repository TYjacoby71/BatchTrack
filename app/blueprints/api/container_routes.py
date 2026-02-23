"""Batch-container API routes.

Synopsis:
Provide authenticated container-management endpoints for batch workflows,
including listing, removal, and adjustment operations via service delegation.

Glossary:
- Container summary: Aggregated container payload attached to a batch.
- Adjustment request: API payload describing container change intent/details.
- Batch integration service: Service layer that executes container operations.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services.batch_integration_service import BatchIntegrationService
from app.utils.permissions import require_permission

# --- Container API blueprint ---
# Purpose: Group batch-container API handlers.
# Inputs: None.
# Outputs: Flask blueprint used by API routing.
container_api_bp = Blueprint("container_api", __name__)


# --- Get batch containers ---
# Purpose: Return container summary data for a specific batch.
# Inputs: Batch id path parameter.
# Outputs: JSON response with container summary or error payload.
@container_api_bp.route("/batches/<int:batch_id>/containers", methods=["GET"])
@login_required
@require_permission("batches.view")
def get_batch_containers(batch_id):
    """Get batch containers using batch integration service"""
    try:
        batch_service = BatchIntegrationService()
        result = batch_service.get_batch_containers_summary(batch_id)

        if not result.get("success"):
            return (
                jsonify({"error": result.get("error", "Failed to get containers")}),
                400,
            )

        return jsonify(result["data"])

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Remove batch container ---
# Purpose: Remove one container association from a batch.
# Inputs: Batch id and container id path parameters.
# Outputs: JSON success/error payload with status code.
@container_api_bp.route(
    "/batches/<int:batch_id>/containers/<int:container_id>", methods=["DELETE"]
)
@login_required
@require_permission("batches.edit")
def remove_batch_container(batch_id, container_id):
    """Remove container from batch using batch integration service"""
    try:
        batch_service = BatchIntegrationService()
        result = batch_service.remove_container_from_batch(batch_id, container_id)

        if result.get("success"):
            return jsonify(
                {"success": True, "message": "Container removed successfully"}
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": result.get("error", "Failed to remove container"),
                    }
                ),
                400,
            )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- Adjust batch container ---
# Purpose: Apply a container adjustment operation for a batch.
# Inputs: Batch/container path ids plus JSON adjustment payload.
# Outputs: JSON success/error payload from service result mapping.
@container_api_bp.route(
    "/batches/<int:batch_id>/containers/<int:container_id>/adjust", methods=["POST"]
)
@login_required
@require_permission("batches.edit")
def adjust_batch_container(batch_id, container_id):
    """Adjust container using batch integration service"""
    try:
        data = request.get_json()
        batch_service = BatchIntegrationService()

        result = batch_service.adjust_batch_container(
            batch_id=batch_id,
            container_id=container_id,
            adjustment_type=data.get("adjustment_type"),
            adjustment_data=data,
        )

        if result.get("success"):
            return jsonify(
                {
                    "success": True,
                    "message": result.get("message", "Container adjusted successfully"),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": result.get("error", "Failed to adjust container"),
                    }
                ),
                400,
            )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
