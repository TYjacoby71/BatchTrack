import logging
from flask import Blueprint, redirect, url_for, flash, request, jsonify
from flask_login import login_required

from ...services.batch_service import BatchOperationsService

fail_batch_bp = Blueprint('fail_batch', __name__)
logger = logging.getLogger(__name__)


@fail_batch_bp.route('/fail/<int:batch_id>', methods=['POST'])
@login_required
def fail_batch(batch_id):
    """Mark an in-progress batch as failed."""
    try:
        failure_reason = request.form.get('reason') if request.form else None
        success, message = BatchOperationsService.fail_batch(batch_id, failure_reason)

        if request.is_json:
            status_code = 200 if success else 400
            payload = {'success': success}
            if success:
                payload['message'] = message
            else:
                payload['error'] = message
            return jsonify(payload), status_code

        if success:
            flash(message or 'Batch marked as failed', 'success')
            return redirect(url_for('batches.list_batches'))
        else:
            flash(message or 'Could not mark batch as failed', 'error')
            return redirect(url_for('batches.view_batch_record', batch_identifier=batch_id))

    except Exception as e:
        logger.error(f"Error failing batch {batch_id}: {str(e)}")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Error failing batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch_record', batch_identifier=batch_id))

