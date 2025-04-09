
from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Batch, Product

batch_view_bp = Blueprint('batch_view', __name__)

@batch_view_bp.route('/batches/<int:batch_id>')
@login_required
def view_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    product = Product.query.filter_by(batch_id=batch_id).first()
    return render_template('view_batch.html', batch=batch, product=product)
