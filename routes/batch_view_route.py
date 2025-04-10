from flask import Blueprint, render_template, abort, flash
from flask_login import login_required
from models import db, Batch

batch_view_bp = Blueprint('batch_view', __name__)

@batch_view_bp.route('/batch-view/batches/<int:batch_id>') #Using the edited route
@login_required
def view_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        return render_template('view_batch.html', batch=batch)
    except Exception as e:
        flash(f'Error viewing batch: {str(e)}')
        abort(500)

@batch_view_bp.route('/batches/list')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batch_list.html', batches=batches)