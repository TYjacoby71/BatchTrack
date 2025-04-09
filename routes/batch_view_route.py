
from flask import Blueprint, render_template, abort, flash
from flask_login import login_required
from models import db, Batch, Product, Recipe
from datetime import datetime

batch_view_bp = Blueprint('batch_view', __name__)

@batch_view_bp.route('/batches/<int:batch_id>')
@login_required
def view_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        product = Product.query.filter_by(batch_id=batch_id).first()
        recipe = Recipe.query.get(batch.recipe_id)
        
        # Calculate batch age in days
        batch_age = (datetime.utcnow() - batch.timestamp).days
        
        return render_template('view_batch.html', 
                             batch=batch, 
                             product=product, 
                             recipe=recipe,
                             batch_age=batch_age)
    except Exception as e:
        flash(f'Error viewing batch: {str(e)}')
        abort(500)

@batch_view_bp.route('/batches/list')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batch_list.html', batches=batches)
