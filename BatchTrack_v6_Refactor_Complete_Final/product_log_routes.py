
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product
from datetime import datetime

class ProductEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(32))  # e.g. sold, spoiled, sample
    note = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

product_log_bp = Blueprint('product_log', __name__)

@product_log_bp.route('/products/<int:product_id>', methods=['GET', 'POST'])
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    events = ProductEvent.query.filter_by(product_id=product_id).order_by(ProductEvent.timestamp.desc()).all()

    if request.method == 'POST':
        event_type = request.form.get('event_type')
        note = request.form.get('note')
        db.session.add(ProductEvent(product_id=product.id, event_type=event_type, note=note))
        db.session.commit()
        flash(f"Logged event: {event_type}")
        return redirect(url_for('product_log.view_product', product_id=product.id))

    return render_template('product_detail.html', product=product, events=events)
