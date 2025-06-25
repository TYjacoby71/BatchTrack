
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from ...models import db, ProductSKU, InventoryItem
from ...services.product_service import ProductService
from ...utils.unit_utils import get_global_unit_list
from . import products_bp

@products_bp.route('/<product_name>/variants/new', methods=['POST'])
@login_required
def add_variant(product_name):
    """Quick add new product variant via AJAX"""
    if request.is_json:
        data = request.get_json()
        variant_name = data.get('name')
        sku_code = data.get('sku')
        description = data.get('description')
        size_label = data.get('size_label', 'Bulk')

        if not variant_name:
            return jsonify({'error': 'Variant name is required'}), 400

        # Check if SKU already exists
        existing_sku = ProductSKU.query.filter_by(
            product_name=product_name, 
            variant_name=variant_name,
            size_label=size_label
        ).first()
        
        if existing_sku:
            return jsonify({'error': 'Variant already exists'}), 400

        try:
            # Create new SKU
            sku = ProductService.get_or_create_sku(
                product_name=product_name,
                variant_name=variant_name,
                size_label=size_label,
                sku_code=sku_code,
                variant_description=description
            )
            
            db.session.commit()

            return jsonify({
                'success': True,
                'variant': {
                    'id': sku.id,
                    'name': sku.variant_name,
                    'sku': sku.sku_code
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    return jsonify({'error': 'Invalid request'}), 400

@products_bp.route('/<product_name>/variant/<variant_name>')
@login_required
def view_variant(product_name, variant_name):
    """View individual product variation details"""
    # Get all SKUs for this product/variant combination
    skus = ProductSKU.query.filter_by(
        product_name=product_name,
        variant_name=variant_name,
        is_active=True
    ).all()

    if not skus:
        flash('Variant not found', 'error')
        return redirect(url_for('products.list_products'))

    # Group SKUs by size_label
    size_groups = {}
    for sku in skus:
        display_size_label = sku.size_label or "Bulk"
        key = f"{display_size_label}_{sku.unit}"
        
        if key not in size_groups:
            size_groups[key] = {
                'size_label': display_size_label,
                'unit': sku.unit,
                'total_quantity': 0,
                'skus': []
            }
        
        size_groups[key]['total_quantity'] += sku.current_quantity
        size_groups[key]['skus'].append(sku)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    return render_template('products/view_variation.html',
                         product_name=product_name,
                         variant_name=variant_name,
                         variant_description=skus[0].variant_description if skus else None,
                         size_groups=size_groups,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list)

@products_bp.route('/<product_name>/variant/<variant_name>/edit', methods=['POST'])
@login_required
def edit_variant(product_name, variant_name):
    """Edit product variation details"""
    name = request.form.get('name')
    description = request.form.get('description')

    if not name:
        flash('Variant name is required', 'error')
        return redirect(url_for('products.view_variant', 
                               product_name=product_name, 
                               variant_name=variant_name))

    # Check if another variant has this name for the same product
    existing = ProductSKU.query.filter(
        ProductSKU.variant_name == name,
        ProductSKU.product_name == product_name,
        ProductSKU.variant_name != variant_name
    ).first()
    
    if existing:
        flash('Another variant with this name already exists for this product', 'error')
        return redirect(url_for('products.view_variant', 
                               product_name=product_name, 
                               variant_name=variant_name))

    # Update all SKUs with this variant name
    skus = ProductSKU.query.filter_by(
        product_name=product_name,
        variant_name=variant_name
    ).all()
    
    for sku in skus:
        sku.variant_name = name
        sku.variant_description = description if description else None

    db.session.commit()
    flash('Variant updated successfully', 'success')
    
    return redirect(url_for('products.view_variant', 
                           product_name=product_name, 
                           variant_name=name))
