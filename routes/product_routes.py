
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product, ProductEvent, InventoryItem
from datetime import datetime
from werkzeug.utils import secure_filename
import os

product_bp = Blueprint('product', __name__)

@product_bp.route('/products')
@login_required
def list_products():
    products = Product.query.order_by(Product.created_at).all()
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
        product.quantity = request.form.get('quantity')
        product.unit = request.form.get('unit')
        product.expiration_date = datetime.strptime(request.form.get('expiration_date'), '%Y-%m-%d').date()
        file = request.files.get('image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            path = os.path.join('static/product_images', filename)
            file.save(path)
            product.image = path
        db.session.commit()
        flash('Product updated.')
        return redirect(url_for('product.view_product', product_id=product.id))
    return render_template('edit_product.html', product=product)
