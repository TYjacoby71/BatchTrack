# Updated SKU adjustment logic to use the universal inventory adjustment service.

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
            self.variant_count = data.get('sku_count', 0)
            self.created_at = data.get('last_updated')
            self.variations = []
            self.inventory = []
            # Calculate total quantity from inventory
            self.total_quantity = data.get('total_quantity', 0)
            # Add product ID for URL generation
            self.id = data.get('product_id', None)

    # Get product IDs for the summary objects
    enhanced_product_data = []
    for data in product_data:
        # Get the first SKU ID for this product to use as product_id
        first_sku = ProductSKU.query.filter_by(
            product_name=data['product_name'],
            organization_id=current_user.organization_id,
            is_active=True
        ).first()
        if first_sku:
            data['product_id'] = first_sku.id
            enhanced_product_data.append(data)

    products = [ProductSummary(data) for data in enhanced_product_data]

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
        unit = request.form.get('product_base_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not unit:
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
            variant_name='Base',
            size_label='Bulk',
            unit=unit,
            sku_code=sku_code,
            low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
            organization_id=current_user.organization_id
        )
        db.session.add(sku)
        db.session.commit()

        flash('Product created successfully', 'success')
        return redirect(url_for('products.view_product', product_name=name))

    units = get_global_unit_list()
    return render_template('products/new_product.html', units=units)

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with all SKUs by product ID"""
    from ...services.product_service import ProductService

    # Get the base SKU to find the product name - with org scoping
    base_sku = ProductSKU.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not base_sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))
        
    product_name = base_sku.product_name

    # Get all SKUs for this product - with org scoping
    skus = ProductSKU.query.filter_by(
        product_name=product_name,
        is_active=True,
        organization_id=current_user.organization_id
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
                'description': sku.description,
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
        'id': product_id,
        'name': product_name,
        'product_base_unit': skus[0].unit if skus else None,
        'low_stock_threshold': skus[0].low_stock_threshold if skus else 0,
        'created_at': skus[0].created_at if skus else None,
        'variations': [type('Variation', (), {
            'name': variant_name,
            'description': variant_data['description'],
            'id': variant_data['skus'][0].id if variant_data['skus'] else None,
            'sku': variant_data['skus'][0].sku_code if variant_data['skus'] else None
        })() for variant_name, variant_data in variants.items()]
    })()

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
    
    return redirect(url_for('products.view_product', product_id=sku.id))

@products_bp.route('/sku/<int:sku_id>')
@login_required
def view_sku(sku_id):
    """View individual SKU details"""
    sku = ProductSKU.query.get_or_404(sku_id)

    # Get SKU history for this specific SKU
    history = ProductSKUHistory.query.filter_by(sku_id=sku_id).order_by(ProductSKUHistory.timestamp.desc()).all()

    # Calculate total quantity from current_quantity
    total_quantity = sku.current_quantity or 0

    return render_template('products/view_sku.html',
                         sku=sku,
                         history=history,
                         total_quantity=total_quantity,
                         get_global_unit_list=get_global_unit_list)

@products_bp.route('/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    """Edit product details by product ID"""
    # Get the base SKU to find the product name - with org scoping
    base_sku = ProductSKU.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not base_sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))
        
    current_product_name = base_sku.product_name
    
    name = request.form.get('name')
    unit = request.form.get('product_base_unit')
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not unit:
        flash('Name and product base unit are required', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Check if another product has this name
    existing = ProductSKU.query.filter(
        ProductSKU.product_name == name,
        ProductSKU.product_name != current_product_name
    ).first()
    if existing:
        flash('Another product with this name already exists', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Update all SKUs for this product
    skus = ProductSKU.query.filter_by(product_name=current_product_name).all()
    for sku in skus:
        sku.product_name = name
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
        # Get the base SKU to find the product name - with org scoping
        base_sku = ProductSKU.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()
        
        if not base_sku:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))
            
        product_name = base_sku.product_name
        
        # Get all SKUs for this product - with org scoping
        skus = ProductSKU.query.filter_by(
            product_name=product_name,
            organization_id=current_user.organization_id
        ).all()

        if not skus:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        # Check if any SKU has inventory
        total_inventory = sum(sku.current_quantity for sku in skus)
        if total_inventory > 0:
            flash('Cannot delete product with remaining inventory', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

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
        return redirect(url_for('products.view_product', product_id=product_id))

@products_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku(sku_id):
    """Adjust SKU inventory"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        flash('SKU not found', 'error')
        return redirect(url_for('products.product_list'))
    quantity = int(request.form.get('quantity'))
    change_type = request.form.get('change_type')
    notes = request.form.get('notes')

    try:
        # Get additional product-specific parameters
        customer = request.form.get('customer')
        sale_price = request.form.get('sale_price')
        order_id = request.form.get('order_id')

        # Convert sale_price to float if provided
        sale_price_float = None
        if sale_price:
            try:
                sale_price_float = float(sale_price)
            except (ValueError, TypeError):
                pass

        # Use centralized inventory adjustment service
        from app.services.inventory_adjustment import process_inventory_adjustment

        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=quantity,
            change_type=change_type,
            unit=sku.unit,
            notes=notes,
            created_by=current_user.id,
            item_type='sku',
            customer=customer,
            sale_price=sale_price_float,
            order_id=order_id
        )

        if success:
            flash(f'SKU inventory adjusted successfully', 'success')
        else:
            flash('Error adjusting inventory', 'error')

        return redirect(url_for('products.view_sku', sku_id=sku_id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error adjusting inventory: {str(e)}', 'error')
        return redirect(url_for('products.view_sku', sku_id=sku_id))

# API routes moved to product_api.py for better organization