from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ...models import db, Product, ProductVariant, ProductSKU, ProductSKUHistory, InventoryItem
from ...services.product_service import ProductService
from ...utils.unit_utils import get_global_unit_list
from datetime import datetime
from werkzeug.utils import secure_filename
import os

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@products_bp.route('/list')
@login_required
def product_list():
    """List all products with inventory summary and sorting"""
    from ...models.product import Product
    
    sort_type = request.args.get('sort', 'name')
    
    # Get all products with their SKUs and inventory items loaded
    products = Product.query.filter_by(
        organization_id=current_user.organization_id,
        is_active=True
    ).options(
        db.joinedload(Product.skus).joinedload(ProductSKU.inventory_item),
        db.joinedload(Product.variants)
    ).all()

    # Sort products based on the requested sort type
    if sort_type == 'popular':
        # Sort by total inventory quantity (most stock first)
        products.sort(key=lambda p: sum(sku.inventory_item.quantity for sku in p.skus if sku.is_active and sku.inventory_item), reverse=True)
    elif sort_type == 'stock':
        # Sort by stock level (low stock first)
        products.sort(key=lambda p: sum(sku.inventory_item.quantity for sku in p.skus if sku.is_active and sku.inventory_item))
    else:  # default to name
        products.sort(key=lambda p: p.name.lower())

    return render_template('products/list_products.html', products=products, current_sort=sort_type)

# Add alias for backward compatibility
list_products = product_list

@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        unit = request.form.get('product_base_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not unit:
            flash('Name and product base unit are required', 'error')
            return redirect(url_for('products.new_product'))

        # Check if product already exists (check both new Product model and legacy ProductSKU)
        from ...models.product import Product, ProductVariant
        existing_product = Product.query.filter_by(
            name=name,
            organization_id=current_user.organization_id
        ).first()

        # Also check legacy ProductSKU table
        existing_sku = ProductSKU.query.filter_by(
            product_name=name,
            organization_id=current_user.organization_id
        ).first()

        if existing_product or existing_sku:
            flash('Product with this name already exists', 'error')
            return redirect(url_for('products.new_product'))

        try:
            # Step 1: Create the main Product
            product = Product(
                name=name,
                base_unit=unit,
                low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(product)
            db.session.flush()  # Get the product ID

            # Step 2: Create the base ProductVariant named "Base"
            variant = ProductVariant(
                product_id=product.id,
                name='Base',
                description='Default base variant',
                organization_id=current_user.organization_id
            )
            db.session.add(variant)
            db.session.flush()  # Get the variant ID

            # Step 3: Create inventory item for the SKU
            inventory_item = InventoryItem(
                name=f"{name} - Base - Bulk",
                type='product',  # Critical: mark as product type
                unit=unit,
                quantity=0.0,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()  # Get the inventory_item ID

            # Step 4: Create the base SKU with "Bulk" size label
            from ...services.product_service import ProductService
            sku_code = ProductService.generate_sku_code(name, 'Base', 'Bulk')
            sku = ProductSKU(
                # New foreign key relationships
                product_id=product.id,
                variant_id=variant.id,
                size_label='Bulk',
                sku_code=sku_code,
                unit=unit,
                low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
                organization_id=current_user.organization_id,
                created_by=current_user.id,
                # Link to inventory item
                inventory_item_id=inventory_item.id,
                is_active=True,
                is_product_active=True
            )
            db.session.add(sku)
            db.session.commit()

            flash('Product created successfully', 'success')
            return redirect(url_for('products.view_product', product_id=sku.inventory_item_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'error')
            return redirect(url_for('products.new_product'))

    units = get_global_unit_list()
    return render_template('products/new_product.html', units=units)

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with all SKUs by product ID"""
    from ...services.product_service import ProductService

    # Get the base SKU to find the product - with org scoping
    base_sku = ProductSKU.query.filter_by(
        inventory_item_id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not base_sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    product = base_sku.product

    # Get all SKUs for this product - with org scoping
    skus = ProductSKU.query.filter_by(
        product_id=product.id,
        is_active=True,
        organization_id=current_user.organization_id
    ).all()

    if not skus:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    # Group SKUs by variant
    variants = {}
    for sku in skus:
        variant_key = sku.variant.name
        if variant_key not in variants:
            variants[variant_key] = {
                'name': sku.variant.name,
                'description': sku.variant.description,
                'skus': []
            }
        variants[variant_key]['skus'].append(sku)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    # Use the actual Product model
    # Add variations for template compatibility
    product.variations = [type('Variation', (), {
        'name': variant_name,
        'description': variant_data['description'],
        'id': variant_data['skus'][0].inventory_item_id if variant_data['skus'] else None,
        'sku': variant_data['skus'][0].sku_code if variant_data['skus'] else None
    })() for variant_name, variant_data in variants.items()]

    # Also add skus to product for template compatibility
    product.skus = skus

    return render_template('products/view_product.html',
                         product=product,
                         variants=variants,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list,
                         inventory_groups={})

# Keep the old route for backward compatibility
@products_bp.route('/<product_name>')
@login_required
def view_product_by_name(product_name):
    """Redirect to product by ID for backward compatibility"""
    # Find the first SKU for this product to get the ID
    sku = ProductSKU.query.filter_by(
        product_name=product_name,
        is_active=True
    ).first()

    if not sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    return redirect(url_for('products.view_product', product_id=sku.inventory_item_id))



@products_bp.route('/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    """Edit product details by product ID"""
    # Get the base SKU to find the product - with org scoping
    base_sku = ProductSKU.query.filter_by(
        inventory_item_id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not base_sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    product = base_sku.product

    name = request.form.get('name')
    unit = request.form.get('product_base_unit')
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not unit:
        flash('Name and product base unit are required', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Check if another product has this name
    from ...models.product import Product
    existing = Product.query.filter(
        Product.name == name,
        Product.id != product.id,
        Product.organization_id == current_user.organization_id
    ).first()
    if existing:
        flash('Another product with this name already exists', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Update the product
    product.name = name
    product.base_unit = unit
    product.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    # Update all SKUs for this product
    skus = ProductSKU.query.filter_by(product_id=product.id).all()
    for sku in skus:
        sku.unit = unit
        sku.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    db.session.commit()
    flash('Product updated successfully', 'success')
    return redirect(url_for('products.view_product', product_id=product_id))

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product and all its related data by product ID"""
    try:
        # Get the base SKU to find the product - with org scoping
        base_sku = ProductSKU.query.filter_by(
            inventory_item_id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not base_sku:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        product = base_sku.product

        # Get all SKUs for this product - with org scoping
        skus = ProductSKU.query.filter_by(
            product_id=product.id,
            organization_id=current_user.organization_id
        ).all()

        if not skus:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        # Check if any SKU has inventory
        total_inventory = sum((sku.inventory_item.quantity if sku.inventory_item else 0.0) for sku in skus)
        if total_inventory > 0:
            flash('Cannot delete product with remaining inventory', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        # Delete history records first
        for sku in skus:
            ProductSKUHistory.query.filter_by(sku_id=sku.id).delete()

        # Delete the SKUs
        ProductSKU.query.filter_by(product_id=product.id).delete()

        # Delete the product and its variants
        from ...models.product import Product, ProductVariant
        ProductVariant.query.filter_by(product_id=product.id).delete()
        Product.query.filter_by(id=product.id).delete()

        db.session.commit()

        flash(f'Product "{product.name}" deleted successfully', 'success')
        return redirect(url_for('products.product_list'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

# Legacy adjust_sku route removed - use product_inventory routes instead

# API routes moved to product_api.py for better organizationpython
# Applying the requested changes to fix route references in products.py
