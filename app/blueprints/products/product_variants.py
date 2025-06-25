from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from ...models import db, Product, ProductVariation, ProductInventory, ProductEvent, InventoryItem
from ...utils.unit_utils import get_global_unit_list
from . import products_bp

@products_bp.route('/<int:product_id>/variants/new', methods=['POST'])
@login_required
def add_variant(product_id):
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

@products_bp.route('/<int:product_id>/variant/<int:variation_id>')
@login_required
def view_variant(product_id, variation_id):
    """View individual product variation details"""
    product = Product.query.get_or_404(product_id)
    variation = ProductVariation.query.get_or_404(variation_id)

    # Ensure variation belongs to this product
    if variation.product_id != product_id:
        flash('Variation not found for this product', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Get inventory for this specific variation
    inventory_entries = ProductInventory.query.filter_by(
        product_id=product_id,
        variant_id=variation.id
    ).order_by(ProductInventory.id.asc()).all()

    # Group by size_label and unit
    size_groups = {}
    for entry in inventory_entries:
        if entry.quantity > 0:  # Only show active inventory
            key = f"{entry.size_label}_{entry.unit}"
            if key not in size_groups:
                size_groups[key] = {
                    'size_label': entry.size_label,
                    'unit': entry.unit,
                    'total_quantity': 0,
                    'batches': []
                }
            size_groups[key]['total_quantity'] += entry.quantity
            size_groups[key]['batches'].append(entry)

    # Get recent activity for this variation
    recent_events = ProductEvent.query.filter(
        ProductEvent.product_id == product_id,
        ProductEvent.description.like(f'%{variation.name}%')
    ).order_by(ProductEvent.timestamp.desc()).limit(20).all()

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    return render_template('products/view_variation.html',
                         product=product,
                         variation=variation,
                         size_groups=size_groups,
                         recent_events=recent_events,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list)

@products_bp.route('/<int:product_id>/variant/<int:variation_id>/edit', methods=['POST'])
@login_required
def edit_variant(product_id, variation_id):
    """Edit product variation details"""
    product = Product.query.get_or_404(product_id)
    variation = ProductVariation.query.get_or_404(variation_id)

    # Ensure variation belongs to this product
    if variation.product_id != product_id:
        flash('Variation not found for this product', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    name = request.form.get('name')
    description = request.form.get('description')

    if not name:
        flash('Variation name is required', 'error')
        return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))

    # Check if another variation has this name for the same product
    existing = ProductVariation.query.filter(
        ProductVariation.name == name,
        ProductVariation.product_id == product_id,
        ProductVariation.id != variation_id
    ).first()
    if existing:
        flash('Another variation with this name already exists for this product', 'error')
        return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))

    variation.name = name
    variation.description = description if description else None

    db.session.commit()
    flash('Variation updated successfully', 'success')
    return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))