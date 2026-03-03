"""Start batch routes.

Synopsis:
Starts a new batch from a server-built plan snapshot.

Glossary:
- Plan snapshot: Immutable payload used to start a batch.
- Batch start: Creates an in-progress batch and inventory deductions.
"""
import logging

from flask import Blueprint, current_app, flash, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Recipe
from app.services.production_planning.service import PlanProductionService
from app.utils.permissions import (
    has_permission,
    has_tier_permission,
    require_permission,
)

from ...services.batch_service import BatchOperationsService

logger = logging.getLogger(__name__)


start_batch_bp = Blueprint("start_batch", __name__)


# =========================================================
# START BATCH
# =========================================================
# --- Start batch ---
# Purpose: Build a plan snapshot and create a new batch.
# Inputs: JSON payload with recipe, scale, batch type, notes, and containers.
# Outputs: JSON response containing started batch id or error details.
@start_batch_bp.route("/start_batch", methods=["POST"])
@login_required
@require_permission("batches.create")
def start_batch():
    """Start a new batch - thin controller delegating to service"""
    try:
        # Get request data
        data = request.get_json()
        recipe_id = data.get("recipe_id")
        scale = float(data.get("scale", 1.0))
        requested_batch_type = data.get("batch_type", "ingredient")
        org_tracks_batch_outputs = has_tier_permission(
            "batches.track_inventory_outputs",
            default_if_missing_catalog=False,
        )
        batch_type = requested_batch_type
        if not org_tracks_batch_outputs:
            current_app.logger.info(
                "🔒 START_BATCH endpoint: Org %s tier disables tracked outputs; forcing untracked batch_type",
                getattr(current_user, "organization_id", None),
            )
            batch_type = "untracked"
        elif batch_type == "product" and not has_permission(
            current_user, "products.create"
        ):
            current_app.logger.info(
                "🔒 START_BATCH endpoint: User %s lacks products.create; forcing ingredient batch_type",
                getattr(current_user, "id", None),
            )
            batch_type = "ingredient"
        notes = data.get("notes", "")
        containers_data = data.get("containers", [])
        data.get("requires_containers", False)
        portioning_data = data.get("portioning_data")

        if current_app.debug:
            current_app.logger.debug("START_BATCH payload: %s", data)
            current_app.logger.debug(
                "START_BATCH portioning_data: %s (type=%s)",
                portioning_data,
                type(portioning_data),
            )

            if portioning_data:
                keys_repr = (
                    list(portioning_data.keys())
                    if isinstance(portioning_data, dict)
                    else "NOT A DICT"
                )
                current_app.logger.debug("START_BATCH portioning keys: %s", keys_repr)
                if isinstance(portioning_data, dict):
                    for key, value in portioning_data.items():
                        current_app.logger.debug(
                            "START_BATCH portioning[%s]=%s (type=%s)",
                            key,
                            value,
                            type(value),
                        )
            else:
                current_app.logger.debug(
                    "START_BATCH portioning_data missing from request"
                )

            batch_data = data.get("batch_data")
            if batch_data and isinstance(batch_data, dict):
                batch_portioning = batch_data.get("portioning_data")
                current_app.logger.debug(
                    "START_BATCH batch_data.portioning_data: %s", batch_portioning
                )
                if batch_portioning and not portioning_data:
                    current_app.logger.debug(
                        "START_BATCH using portioning_data from batch_data fallback"
                    )
                    portioning_data = batch_portioning
        else:
            batch_data = data.get("batch_data")

        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            flash("Recipe not found.", "error")
            return jsonify({"error": "Recipe not found"}), 404

        snapshot_obj = PlanProductionService.build_plan(
            recipe=recipe,
            scale=scale,
            batch_type=batch_type,
            notes=notes,
            containers=containers_data,
        )
        plan_dict = snapshot_obj.to_dict()
        batch, errors = BatchOperationsService.start_batch(plan_dict)

        if not batch:
            # If batch is None, errors contains the error message
            flash(f"Failed to start batch: {', '.join(errors)}", "error")
            return jsonify({"error": "Failed to start batch"}), 400

        if errors:
            # Batch was created but with warnings
            flash(f"Batch started with warnings: {', '.join(errors)}", "warning")
        else:
            # Build success message
            deduction_summary = []
            for ing in batch.batch_ingredients:
                deduction_summary.append(
                    f"{ing.quantity_used} {ing.unit} of {ing.inventory_item.name}"
                )
            for cont in batch.containers:
                deduction_summary.append(
                    f"{cont.quantity_used} units of {cont.inventory_item.container_display_name}"
                )

            if deduction_summary:
                deducted_items = ", ".join(deduction_summary)
                flash(
                    f"Batch started successfully. Deducted items: {deducted_items}",
                    "success",
                )
            else:
                flash("Batch started successfully", "success")

        return jsonify({"batch_id": batch.id})

    except Exception as e:
        logger.warning("Suppressed exception fallback at app/blueprints/batches/start_batch.py:158", exc_info=True)
        flash(f"Error starting batch: {str(e)}", "error")
        return jsonify({"error": str(e)}), 500
