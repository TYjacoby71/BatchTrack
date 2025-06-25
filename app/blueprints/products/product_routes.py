from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ...models import db, Product, ProductEvent, InventoryItem, ProductVariation
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from ...blueprints.fifo.services import deduct_fifo
from ...utils.unit_utils import get_global_unit_list

from . import products_bp

@products_bp.route('/products')
@login_required
def list_products():
    products = Product.query.order_by(Product.created_at).all()
    return render_template('products/list_products.html', products=products)

@products_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        product_base_unit = request.form.get('product_base_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not product_base_unit:
            flash('Name and product base unit are required', 'error')
            return redirect(url_for('products.new_product'))

        # Check if product already exists
        existing = Product.query.filter_by(name=name).first()
        if existing:
            flash('Product with this name already exists', 'error')
            return redirect(url_for('products.new_product'))

        product = Product(
            name=name,
            product_base_unit=product_base_unit,
            low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0
        )

        db.session.add(product)
        db.session.flush()  # Get the product ID

        # Create the Base variant automatically
        base_variant = ProductVariation(
            product_id=product.id,
            name='Base',
            description='Default base variant'
        )
        db.session.add(base_variant)
        db.session.commit()

        flash('Product created successfully', 'success')
        return redirect(url_for('products.view_product', product_id=product.id))

    units = get_global_unit_list()
    return render_template('products/new_product.html', units=units)

@products_bp.route('/products/<int:product_id>', methods=['GET', 'POST'])
@login_required
def view_product(product_id):
    from ...models import ProductInventory

    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        event_type = request.form.get('event_type')
        note = request.form.get('note')
        db.session.add(ProductEvent(product_id=product.id, event_type=event_type, note=note))
        db.session.commit()
        flash(f"Logged event: {event_type}")
        return redirect(url_for('products.view_product', product_id=product.id))

    # Get inventory data grouped by variant
    inventory_entries = ProductInventory.query.filter_by(product_id=product_id).all()

    # Group inventory by variant
    inventory_groups = {}
    for entry in inventory_entries:
        variant_key = entry.variant or 'Base'
        if variant_key not in inventory_groups:
            inventory_groups[variant_key] = {
                'variant': variant_key,
                'total_quantity': 0,
                'batches': []
            }
        inventory_groups[variant_key]['total_quantity'] += entry.quantity
        inventory_groups[variant_key]['batches'].append(entry)

    return render_template('products/view_product.html', 
                         product=product, 
                         events=product.events,
                         inventory_groups=inventory_groups)

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

@products_bp.route('/products/<int:product_id>/variant/<int:variation_id>')
@login_required
def view_variant(product_id, variation_id):
    product = Product.query.get_or_404(product_id)
    variation = ProductVariation.query.filter_by(id=variation_id, product_id=product_id).first_or_404()
    return render_template('products/view_variation.html', product=product, variation=variation)

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