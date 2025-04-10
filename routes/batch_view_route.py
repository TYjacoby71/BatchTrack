from flask import Blueprint, render_template, abort, flash, redirect, url_for
from flask_login import login_required
from models import Batch

batch_view_bp = Blueprint('batch_view', __name__)

@batch_view_bp.route('/batches/<int:batch_id>')
@login_required
def view_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        if not batch.total_cost:
            return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))
        return render_template('view_batch.html', 
                             batch=batch)
    except Exception as e:
        flash(f'Error viewing batch: {str(e)}')
        return redirect(url_for('batch_view.list_batches'))

@batch_view_bp.route('/batches/list')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batches_list.html', batches=batches)