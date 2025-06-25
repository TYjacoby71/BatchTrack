from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ...models import db, Product, ProductEvent, InventoryItem
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from ...blueprints.fifo.services import deduct_fifo

from . import products_bp

@products_bp.route('/products')
@login_required
def list_products():
    products = Product.query.order_by(Product.created_at).all()
    return render_template('products/list_products.html', products=products)

@products_bp.route('/products/<int:product_id>', methods=['GET', 'POST'])
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        event_type = request.form.get('event_type')
        note = request.form.get('note')
        db.session.add(ProductEvent(product_id=product.id, event_type=event_type, note=note))
        db.session.commit()
        flash(f"Logged event: {event_type}")
        return redirect(url_for('products.view_product', product_id=product.id))
    return render_template('products/view_product.html', product=product, events=product.events)

@products_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('products.view_product', product_id=product.id))
    return render_template('products/edit_product.html', product=product)

@products_bp.route("/products/<int:product_id>/deduct", methods=["POST"])
@login_required
def deduct_product(product_id):
    from ..services.product_service import ProductService

    variant = request.form.get("variant", "Base")
    size_label = request.form.get("size_label", "Bulk")
    unit = request.form.get("unit")
    reason = request.form.get("reason", "manual_deduction")
    notes = request.form.get("notes", "")

    try:
        quantity = float(request.form.get("quantity", 0))
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        success = ProductService.process_inventory_adjustment(
            product_id=product_id,
            variant=variant,
            size_label=size_label,
            adjustment_type=reason,
            quantity=quantity,
            notes=notes
        )

        if success:
            flash(f"Deducted {quantity} {unit} from {variant} - {size_label} using FIFO", "success")
        else:
            flash("Not enough stock to fulfill request", "danger")

    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash("Error processing deduction request", "danger")

    return redirect(url_for('products.view_product', product_id=product_id))