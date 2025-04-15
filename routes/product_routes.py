
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product, ProductEvent
from datetime import datetime

product_bp = Blueprint('product', __name__)

@product_bp.route('/products')
@login_required
def list_products():
    products = Product.query.all()
    return render_template('product_list.html', products=products)

@product_bp.route('/products/<int:product_id>', methods=['GET', 'POST'])
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        event_type = request.form.get('event_type')
        note = request.form.get('note')
        db.session.add(ProductEvent(product_id=product.id, event_type=event_type, note=note))
        db.session.commit()
        flash(f"Logged event: {event_type}")
        return redirect(url_for('product.view_product', product_id=product.id))
    return render_template('product_detail.html', product=product, events=product.events)

@product_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.default_unit = request.form.get('default_unit')
        product.is_active = bool(request.form.get('is_active', True))
        db.session.commit()
        flash('Product updated.')
        return redirect(url_for('product.view_product', product_id=product.id))
    return render_template('edit_product.html', product=product)
