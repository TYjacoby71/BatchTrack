from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ...services.batch_service import BatchOperationsService
from ...utils import get_setting
from app.utils.permissions import role_required
import logging

logger = logging.getLogger(__name__)

cancel_batch_bp = Blueprint('cancel_batch', __name__)

@cancel_batch_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    """Cancel a batch - thin controller delegating to service"""
    try:
        logger.info(f"🔥 CANCEL ROUTE DEBUG: ===== CANCEL REQUEST START =====")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Cancel request received for batch_id={batch_id}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Current user: {current_user.id}, organization: {current_user.organization_id}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Request method: {request.method}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Request form data: {dict(request.form)}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Request headers: {dict(request.headers)}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Request URL: {request.url}")
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Request endpoint: {request.endpoint}")

        # Delegate to service
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Calling BatchOperationsService.cancel_batch...")
        success, result = BatchOperationsService.cancel_batch(batch_id)

        logger.info(f"🔥 CANCEL ROUTE DEBUG: Service returned - success={success}, result type={type(result)}")

        if not success:
            logger.error(f"🔥 CANCEL ROUTE DEBUG: Cancellation failed: {result}")
            flash(result, "error")
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

        # result is restoration_summary on success
        restoration_summary = result
        logger.info(f"🔥 CANCEL ROUTE DEBUG: Cancellation successful, restoration summary: {restoration_summary}")

        # Show appropriate message based on settings
        settings = get_setting('alerts', {})
        if settings.get('show_inventory_refund', True) and restoration_summary:
            restored_items = ", ".join(restoration_summary)
            flash(f"Batch cancelled. Restored items: {restored_items}", "success")
        else:
            flash("Batch cancelled successfully", "success")

        logger.info(f"🔥 CANCEL ROUTE DEBUG: Redirecting to batches list...")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        logger.error(f"🔥 CANCEL ROUTE DEBUG: Exception in route: {str(e)}")
        import traceback
        logger.error(f"🔥 CANCEL ROUTE DEBUG: Full traceback: {traceback.format_exc()}")
        flash(f"Error cancelling batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))