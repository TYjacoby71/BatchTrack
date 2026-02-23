"""Batch cancellation routes.

Synopsis:
Provide authenticated endpoint for canceling batches through the batch service,
including user feedback about restored inventory items.

Glossary:
- Batch cancellation: Workflow that stops a batch and restores inventory state.
- Restoration summary: Human-readable list of items restored after cancel.
- Batch service delegation: Route-to-service call pattern for cancellation logic.
"""

from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required

from app.utils.permissions import require_permission

from ...services.batch_service import BatchOperationsService
from ...utils import get_setting

# --- Cancel-batch blueprint ---
# Purpose: Group cancellation route registration.
# Inputs: None.
# Outputs: Blueprint namespace for cancel endpoint.
cancel_batch_bp = Blueprint("cancel_batch", __name__)


# --- Cancel batch ---
# Purpose: Delegate batch cancellation and present user-facing flash feedback.
# Inputs: Batch id path parameter.
# Outputs: Redirect response to batch detail/list routes with flash messaging.
@cancel_batch_bp.route("/cancel/<int:batch_id>", methods=["POST"])
@login_required
@require_permission("batches.cancel")
def cancel_batch(batch_id):
    """Cancel a batch - thin controller delegating to service"""
    try:
        # Delegate to service
        success, result = BatchOperationsService.cancel_batch(batch_id)

        if not success:
            flash(result, "error")
            return redirect(
                url_for("batches.view_batch_record", batch_identifier=batch_id)
            )

        # result is restoration_summary on success
        restoration_summary = result

        # Show appropriate message based on settings
        settings = get_setting("alerts", {})
        if settings.get("show_inventory_refund", True) and restoration_summary:
            restored_items = ", ".join(restoration_summary)
            flash(f"Batch cancelled. Restored items: {restored_items}", "success")
        else:
            flash("Batch cancelled successfully", "success")

        return redirect(url_for("batches.list_batches"))

    except Exception as e:
        flash(f"Error cancelling batch: {str(e)}", "error")
        return redirect(url_for("batches.view_batch_record", batch_identifier=batch_id))
