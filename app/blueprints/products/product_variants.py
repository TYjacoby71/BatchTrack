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

        if not variant_name or variant_name.strip() == '':
            return jsonify({'error': 'Variant name is required'}), 400

        # Get the parent product's base unit from existing SKUs
        existing_product_sku = ProductSKU.query.filter_by(product_name=product_name).first()
        if not existing_product_sku:
            return jsonify({'error': 'Parent product not found'}), 404

        parent_unit = existing_product_sku.unit

        # Check if variant already exists for this product
        existing_variant = ProductSKU.query.filter_by(
            product_name=product_name, 
            variant_name=variant_name.strip()
        ).first()

        if existing_variant:
            return jsonify({'error': f'Variant "{variant_name}" already exists for this product'}), 400

        try:
            # Create new SKU with inherited unit and default Bulk size
            sku = ProductService.get_or_create_sku(
                product_name=product_name,
                variant_name=variant_name.strip(),
                size_label='Bulk',  # Always create Bulk size for new variants
                unit=parent_unit,   # Inherit parent product's unit
                sku_code=sku_code,
                variant_description=description
            )

            # Set additional properties BEFORE committing
            sku.description = description
            sku.organization_id = existing_product_sku.organization_id
            sku.low_stock_threshold = existing_product_sku.low_stock_threshold

            db.session.commit()

            return jsonify({
                'success': True,
                'variant': {
                    'id': sku.id,
                    'name': sku.variant_name,
                    'sku': sku.sku_code,
                    'unit': sku.unit,
                    'size_label': sku.size_label
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to create variant: {str(e)}'}), 500

    # Handle form data as well
    variant_name = request.form.get('name')
    sku_code = request.form.get('sku')
    description = request.form.get('description')

    if not variant_name or variant_name.strip() == '':
        return jsonify({'error': 'Variant name is required'}), 400

    try:
        # Get the parent product's base unit from existing SKUs
        existing_product_sku = ProductSKU.query.filter_by(product_name=product_name).first()
        if not existing_product_sku:
            return jsonify({'error': 'Parent product not found'}), 404

        parent_unit = existing_product_sku.unit

        # Check if variant already exists
        existing_variant = ProductSKU.query.filter_by(
            product_name=product_name, 
            variant_name=variant_name.strip()
        ).first()

        if existing_variant:
            return jsonify({'error': f'Variant "{variant_name}" already exists for this product'}), 400

        # Create new SKU with inherited unit
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name.strip(),
            size_label='Bulk',
            unit=parent_unit,
            sku_code=sku_code,
            variant_description=description
        )

        # Set additional properties BEFORE committing
        sku.description = description
        sku.organization_id = existing_product_sku.organization_id
        sku.low_stock_threshold = existing_product_sku.low_stock_threshold

        db.session.commit()

        return jsonify({
            'success': True,
            'variant': {
                'id': sku.id,
                'name': sku.variant_name,
                'sku': sku.sku_code,
                'unit': sku.unit,
                'size_label': sku.size_label
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create variant: {str(e)}'}), 500

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
                'skus': [],
                'batches': []  # Add batches for cost calculations
            }

        size_groups[key]['total_quantity'] += sku.current_quantity
        size_groups[key]['skus'].append(sku)

        # Add batch information for cost calculations
        for batch in sku.batches:
            if batch.quantity > 0:
                size_groups[key]['batches'].append(batch)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    # Create a product object for the template
    product = type('Product', (), {
        'name': product_name,
        'id': skus[0].id if skus else None,
        'product_base_unit': skus[0].unit if skus else None,
        'low_stock_threshold': skus[0].low_stock_threshold if skus else 0
    })()

    # Create a variation object for the template  
    variation = type('Variation', (), {
        'name': variant_name,
        'description': skus[0].description if skus else None,
        'id': skus[0].id if skus else None
    })()

    return render_template('products/view_variation.html',
                         product=product,
                         product_name=product_name,
                         variant_name=variant_name,
                         variation=variation,
                         variant_description=skus[0].description if skus else None,
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

@products_bp.route('/<product_name>/variant/<variant_name>/delete', methods=['POST'])
@login_required
def delete_variant(product_name, variant_name):
    """Delete a product variant and all its SKUs"""
    # Get all SKUs for this variant
    skus = ProductSKU.query.filter_by(
        product_name=product_name,
        variant_name=variant_name
    ).all()

    if not skus:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_name=product_name))

    # Check if any SKUs have inventory
    has_inventory = any(sku.current_quantity > 0 for sku in skus)
    if has_inventory:
        flash('Cannot delete variant with existing inventory', 'error')
        return redirect(url_for('products.view_variant', 
                               product_name=product_name, 
                               variant_name=variant_name))

    # Delete all SKUs for this variant
    for sku in skus:
        sku.is_active = False

    db.session.commit()

    # Check if this was the last variant for the product
    remaining_variants = ProductSKU.query.filter_by(
        product_name=product_name,
        is_active=True
    ).count()

    if remaining_variants == 0:
        # Auto-create Base variant
        ProductService.ensure_base_variant_if_needed(product_name)
        db.session.commit()
        flash(f'Variant "{variant_name}" deleted. Created default "Base" variant.', 'success')
    else:
        flash(f'Variant "{variant_name}" deleted successfully', 'success')

    return redirect(url_for('products.view_product', product_name=product_name))