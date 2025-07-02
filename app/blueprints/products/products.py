from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, ProductSKU, ProductSKUHistory, InventoryItem
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
    from ...services.product_service import ProductService

    sort_type = request.args.get('sort', 'name')
    product_data = ProductService.get_product_summary_skus()

    # Convert dict data to objects with the attributes the template expects
    class ProductSummary:
        def __init__(self, data):
            self.name = data.get('product_name', '')
            self.product_base_unit = data.get('product_base_unit', '')
            self.variant_count = data.get('variant_count', 0)
            self.created_at = data.get('created_at')
            self.variations = data.get('variations', [])
            self.inventory = data.get('inventory', [])
            # Calculate total quantity from inventory
            self.total_quantity = data.get('total_quantity', 0)

    products = [ProductSummary(data) for data in product_data]

    # Sort products based on the requested sort type
    if sort_type == 'popular':
        # Sort by sales volume (most sales first) - TODO: implement sales tracking for SKUs
        products.sort(key=lambda p: p.total_quantity, reverse=True)
    elif sort_type == 'stock':
        # Sort by stock level (low stock first)
        products.sort(key=lambda p: p.total_quantity)
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
        product_base_unit = request.form.get('product_base_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not product_base_unit:
            flash('Name and product base unit are required', 'error')
            return redirect(url_for('products.new_product'))

        # Check if product already exists
        existing = ProductSKU.query.filter_by(product_name=name).first()
        if existing:
            flash('Product with this name already exists', 'error')
            return redirect(url_for('products.new_product'))

        # Create the base SKU with auto-generated SKU code
        from ...services.product_service import ProductService
        sku_code = ProductService.generate_sku_code(name, 'Base', 'Bulk')
        sku = ProductSKU(
            product_name=name,
            product_base_unit=product_base_unit,
            variant_name='Base',
            size_label='Bulk',
            unit=product_base_unit,
            sku_code=sku_code,
            low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
            variant_description='Default base variant',
            organization_id=current_user.organization_id
        )
        db.session.add(sku)
        db.session.commit()

        flash('Product created successfully', 'success')
        return redirect(url_for('product_inventory.view_sku', sku_id=sku.id))

    units = get_global_unit_list()
    return render_template('products/new_product.html', units=units)

@products_bp.route('/<product_name>')
@login_required
def view_product(product_name):
    """View product details with all SKUs"""
    from ...services.product_service import ProductService

    # Get all SKUs for this product
    skus = ProductSKU.query.filter_by(
        product_name=product_name,
        is_active=True
    ).all()

    if not skus:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    # Group SKUs by variant
    variants = {}
    for sku in skus:
        variant_key = sku.variant_name
        if variant_key not in variants:
            variants[variant_key] = {
                'name': sku.variant_name,
                'description': sku.variant_description,
                'skus': []
            }
        variants[variant_key]['skus'].append(sku)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    # Create a product object for the template
    product = type('Product', (), {
        'name': product_name,
        'product_base_unit': skus[0].product_base_unit if skus else None,
        'low_stock_threshold': skus[0].low_stock_threshold if skus else 0,
        'created_at': skus[0].created_at if skus else None,
        'id': skus[0].id if skus else None,
        'variations': [type('Variation', (), {
            'name': variant_name,
            'description': variant_data['description'],
            'id': variant_data['skus'][0].id if variant_data['skus'] else None,
            'sku': variant_data['skus'][0].sku_code if variant_data['skus'] else None
        })() for variant_name, variant_data in variants.items()]
    })()

    return render_template('products/view_product.html', 
                         product=product,
                         product_name=product_name,
                         product_base_unit=skus[0].product_base_unit if skus else None,
                         variants=variants,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list,
                         inventory_groups={})

@products_bp.route('/<product_name>/edit', methods=['POST'])
@login_required
def edit_product(product_name):
    """Edit product details"""
    name = request.form.get('name')
    product_base_unit = request.form.get('product_base_unit')
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not product_base_unit:
        flash('Name and product base unit are required', 'error')
        return redirect(url_for('products.view_product', product_name=product_name))

    # Check if another product has this name
    existing = ProductSKU.query.filter(
        ProductSKU.product_name == name,
        ProductSKU.product_name != product_name
    ).first()
    if existing:
        flash('Another product with this name already exists', 'error')
        return redirect(url_for('products.view_product', product_name=product_name))

    # Update all SKUs for this product
    skus = ProductSKU.query.filter_by(product_name=product_name).all()
    for sku in skus:
        sku.product_name = name
        sku.product_base_unit = product_base_unit
        sku.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    db.session.commit()
    flash('Product updated successfully', 'success')
    return redirect(url_for('products.view_product', product_name=name))

@products_bp.route('/<product_name>/delete', methods=['POST'])
@login_required
def delete_product(product_name):
    """Delete a product and all its related data"""
    try:
        # Get all SKUs for this product
        skus = ProductSKU.query.filter_by(product_name=product_name).all()

        if not skus:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        # Check if any SKU has inventory
        total_inventory = sum(sku.current_quantity for sku in skus)
        if total_inventory > 0:
            flash('Cannot delete product with remaining inventory', 'error')
            return redirect(url_for('products.view_product', product_name=product_name))

        # Delete history records first
        for sku in skus:
            ProductSKUHistory.query.filter_by(sku_id=sku.id).delete()

        # Delete the SKUs
        ProductSKU.query.filter_by(product_name=product_name).delete()
        db.session.commit()

        flash(f'Product "{product_name}" deleted successfully', 'success')
        return redirect(url_for('products.product_list'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        return redirect(url_for('products.view_product', product_name=product_name))