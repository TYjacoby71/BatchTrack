
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ...models import db, Product, ProductVariation
from ...utils.template_helpers import get_global_unit_list

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def product_list():
    """List all products with inventory summary and sorting"""
    from services.product_service import ProductService
    
    sort_type = request.args.get('sort', 'name')
    products = ProductService.get_product_summary()

    # Sort products based on the requested sort type
    if sort_type == 'popular':
        # Sort by sales volume (most sales first)
        sales_data = ProductService.get_product_sales_volume()
        sales_dict = {item['product_id']: item['total_sales'] for item in sales_data}
        products.sort(key=lambda p: sales_dict.get(p.id, 0), reverse=True)
    elif sort_type == 'stock':
        # Sort by stock level (low stock first)
        products.sort(key=lambda p: p.total_inventory / max(p.low_stock_threshold, 1))
    else:  # default to name
        products.sort(key=lambda p: p.name.lower())

    return render_template('products/list_products.html', products=products, current_sort=sort_type)

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

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with FIFO inventory"""
    from services.product_service import ProductService
    from ...models import InventoryItem

    product = Product.query.get_or_404(product_id)
    inventory_groups = ProductService.get_fifo_inventory_groups(product_id)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    return render_template('products/view_product.html', 
                         product=product, 
                         inventory_groups=inventory_groups,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list)

@products_bp.route('/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    """Edit product details"""
    product = Product.query.get_or_404(product_id)

    name = request.form.get('name')
    product_base_unit = request.form.get('product_base_unit')
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not product_base_unit:
        flash('Name and product base unit are required', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Check if another product has this name
    existing = Product.query.filter(Product.name == name, Product.id != product_id).first()
    if existing:
        flash('Another product with this name already exists', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    product.name = name
    product.product_base_unit = product_base_unit
    product.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    db.session.commit()
    flash('Product updated successfully', 'success')
    return redirect(url_for('products.view_product', product_id=product_id))

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product and all its related data"""
    from ...models import ProductInventoryHistory, ProductInventory, ProductEvent

    product = Product.query.get_or_404(product_id)

    try:
        # Check if product has any batches
        if product.batches:
            flash('Cannot delete product with associated batches', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        # Delete related records in order
        ProductInventoryHistory.query.filter(
            ProductInventoryHistory.product_inventory_id.in_(
                db.session.query(ProductInventory.id).filter_by(product_id=product_id)
            )
        ).delete(synchronize_session=False)

        # Delete product inventory
        ProductInventory.query.filter_by(product_id=product_id).delete()

        # Delete product events
        ProductEvent.query.filter_by(product_id=product_id).delete()

        # Delete product variations
        ProductVariation.query.filter_by(product_id=product_id).delete()

        # Delete the product itself
        db.session.delete(product)
        db.session.commit()

        flash(f'Product "{product.name}" deleted successfully', 'success')
        return redirect(url_for('products.product_list'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))
