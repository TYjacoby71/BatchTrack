from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Product, ProductVariation, ProductInventory, ProductEvent, Batch, InventoryItem
from datetime import datetime
from services.inventory_adjustment import process_inventory_adjustment

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def list_products():
    """List all products with inventory summary"""
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    # Calculate inventory totals for each product
    for product in products:
        product.total_inventory = sum(inv.quantity for inv in product.inventory if inv.quantity > 0)
        product.variant_count = len(product.variations)

    return render_template('products/list_products.html', products=products)

@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        default_unit = request.form.get('default_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not default_unit:
            flash('Name and default unit are required', 'error')
            return redirect(url_for('products.new_product'))

        # Check if product already exists
        existing = Product.query.filter_by(name=name).first()
        if existing:
            flash('Product with this name already exists', 'error')
            return redirect(url_for('products.new_product'))

        product = Product(
            name=name,
            default_unit=default_unit,
            low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0
        )

        db.session.add(product)
        db.session.commit()

        flash('Product created successfully', 'success')
        return redirect(url_for('products.view_product', product_id=product.id))

    # Get product units for dropdown
    from models import ProductUnit
    product_units = ProductUnit.query.all()

    return render_template('products/new_product.html', product_units=product_units)

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with FIFO inventory"""
    product = Product.query.get_or_404(product_id)

    # Get FIFO-ordered inventory grouped by variant and size
    inventory_groups = {}
    for inv in product.inventory:
        if inv.quantity > 0:
            key = f"{inv.variant or 'Default'}_{inv.unit}"
            if key not in inventory_groups:
                inventory_groups[key] = {
                    'variant': inv.variant or 'Default',
                    'unit': inv.unit,
                    'total_quantity': 0,
                    'batches': [],
                    'avg_cost': 0
                }
            inventory_groups[key]['batches'].append(inv)
            inventory_groups[key]['total_quantity'] += inv.quantity

    # Calculate average weighted cost for each group
    for group in inventory_groups.values():
        total_cost = sum(inv.quantity * (inv.batch.total_cost / inv.batch.final_quantity if inv.batch and inv.batch.final_quantity else 0) for inv in group['batches'])
        group['avg_cost'] = total_cost / group['total_quantity'] if group['total_quantity'] > 0 else 0
        group['batches'].sort(key=lambda x: x.timestamp)  # FIFO order

    return render_template('products/view_product.html', 
                         product=product, 
                         inventory_groups=inventory_groups)

@products_bp.route('/<int:product_id>/variant/<variant>/size/<size>/unit/<unit>')
@login_required
def view_batches_by_variant(product_id, variant, size, unit):
    """View FIFO-ordered batches for a specific product variant"""
    product = Product.query.get_or_404(product_id)

    batches = ProductInventory.query.filter_by(
        product_id=product_id,
        variant=variant,
        unit=unit
    ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

    return render_template('products/batches_by_variant.html',
                         product=product,
                         batches=batches,
                         variant=variant,
                         size=size,
                         unit=unit)

@products_bp.route('/<int:product_id>/variants/new', methods=['POST'])
@login_required
def add_variant():
    """Quick add new product variant via AJAX"""
    if request.is_json:
        data = request.get_json()
        product_id = data.get('product_id')
        variant_name = data.get('name')
        sku = data.get('sku')
        description = data.get('description')

        product = Product.query.get_or_404(product_id)

        # Check if variant already exists
        if ProductVariation.query.filter_by(product_id=product_id, name=variant_name).first():
            return jsonify({'error': 'Variant already exists'}), 400

        variant = ProductVariation(
            product_id=product_id,
            name=variant_name,
            sku=sku,
            description=description
        )
        db.session.add(variant)
        db.session.commit()

        return jsonify({
            'success': True,
            'variant': {
                'id': variant.id,
                'name': variant.name,
                'sku': variant.sku
            }
        })

    return jsonify({'error': 'Invalid request'}), 400

@products_bp.route('/<int:product_id>/deduct', methods=['POST'])
@login_required
def deduct_product(product_id):
    """Deduct product inventory using FIFO"""
    product = Product.query.get_or_404(product_id)
    variant = request.form.get('variant', 'Default')
    unit = request.form.get('unit')
    quantity = float(request.form.get('quantity', 0))
    reason = request.form.get('reason', 'manual_deduction')
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Get FIFO-ordered inventory for this variant
    inventory_items = ProductInventory.query.filter_by(
        product_id=product_id,
        variant=variant,
        unit=unit
    ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

    remaining_to_deduct = quantity
    deducted_items = []

    for item in inventory_items:
        if remaining_to_deduct <= 0:
            break

        if item.quantity <= remaining_to_deduct:
            # Use entire item
            deducted_items.append((item, item.quantity))
            remaining_to_deduct -= item.quantity
            item.quantity = 0
        else:
            # Partial use
            deducted_items.append((item, remaining_to_deduct))
            item.quantity -= remaining_to_deduct
            remaining_to_deduct = 0

    if remaining_to_deduct > 0:
        flash(f'Not enough stock. Only {quantity - remaining_to_deduct} available', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Commit the deductions
    db.session.commit()

    # Log the event
    event_note = f"FIFO deduction: {quantity} {unit} of {variant}. Items used: {len(deducted_items)}. Reason: {reason}"
    if notes:
        event_note += f". Notes: {notes}"

    db.session.add(ProductEvent(
        product_id=product_id,
        event_type='inventory_deduction',
        note=event_note
    ))
    db.session.commit()

    flash(f'Deducted {quantity} {unit} from {variant} using FIFO', 'success')
    return redirect(url_for('products.view_product', product_id=product_id))

@products_bp.route('/<int:product_id>/adjust', methods=['POST'])


@products_bp.route('/api/search', methods=['GET'])
@login_required
def search_products():
    """API endpoint for product/variant search in finish batch modal"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    # Search products by name
    products = Product.query.filter(
        Product.name.ilike(f'%{query}%'),
        Product.is_active == True
    ).limit(10).all()

    result = []
    for product in products:
        product_data = {
            'id': product.id,
            'name': product.name,
            'default_unit': product.default_unit,
            'variants': []
        }

        # Add existing variants
        for variant in product.variations:
            product_data['variants'].append({
                'id': variant.id,
                'name': variant.name,
                'sku': variant.sku
            })

        # Add default variant if no variants exist
        if not product.variations:
            product_data['variants'].append({
                'id': None,
                'name': 'Default',
                'sku': None
            })

        result.append(product_data)

    return jsonify({'products': result})

@products_bp.route('/api/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """Quick add product and/or variant for finish batch modal"""
    data = request.get_json()

    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    default_unit = data.get('default_unit', 'oz')

    if not product_name:
        return jsonify({'error': 'Product name is required'}), 400

    # Check if product exists
    product = Product.query.filter_by(name=product_name).first()

    if not product:
        # Create new product
        product = Product(
            name=product_name,
            default_unit=default_unit
        )
        db.session.add(product)
        db.session.flush()  # Get the ID

    variant = None
    if variant_name and variant_name.lower() != 'default':
        # Check if variant exists
        variant = ProductVariation.query.filter_by(
            product_id=product.id, 
            name=variant_name
        ).first()

        if not variant:
            # Create new variant
            variant = ProductVariation(
                product_id=product.id,
                name=variant_name
            )
            db.session.add(variant)
            db.session.flush()

    db.session.commit()

    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'default_unit': product.default_unit
        },
        'variant': {
            'id': variant.id if variant else None,
            'name': variant.name if variant else 'Default'
        } if variant or variant_name else None
    })

@login_required
def adjust_inventory(product_id):
    """Manual inventory adjustment for specific batch"""
    inventory_id = request.form.get('inventory_id')
    adjustment_type = request.form.get('adjustment_type')  # spoil, trash, recount
    quantity_change = float(request.form.get('quantity_change'))
    notes = request.form.get('notes', '')

    inventory_item = ProductInventory.query.get_or_404(inventory_id)

    if inventory_item.product_id != product_id:
        flash('Invalid inventory item', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    old_quantity = inventory_item.quantity

    if adjustment_type == 'recount':
        inventory_item.quantity = quantity_change
    else:
        inventory_item.quantity += quantity_change

    # Ensure quantity doesn't go negative
    if inventory_item.quantity < 0:
        inventory_item.quantity = 0

    db.session.commit()

    # Log the adjustment
    db.session.add(ProductEvent(
        product_id=product_id,
        event_type=f'inventory_{adjustment_type}',
        note=f'Batch {inventory_item.batch_id}: {old_quantity} → {inventory_item.quantity} {inventory_item.unit}. {notes}'
    ))
    db.session.commit()

    flash(f'Inventory adjusted: {adjustment_type}', 'success')
    return redirect(url_for('products.view_product', product_id=product_id))