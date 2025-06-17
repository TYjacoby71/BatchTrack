from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Product, ProductVariation, ProductInventory, ProductInventoryHistory, Batch
from services.product_service import ProductService, adjust_product_fifo_entry
from datetime import datetime
from services.inventory_adjustment import process_inventory_adjustment
import re
from utils.unit_utils import get_global_unit_list

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.app_template_filter('parse_sale_data')
def parse_sale_data(note):
    """Parse structured data from sale notes"""
    if not note:
        return {'quantity': None, 'sale_price': None, 'customer': None, 'notes': None}

    data = {'quantity': None, 'sale_price': None, 'customer': None, 'notes': None}

    # Parse FIFO deduction format: "FIFO deduction: 2.0 count of Base. Items used: 1. Reason: sale"
    fifo_match = re.search(r'FIFO deduction:\s*([\d.]+)\s*\w+', note)
    if fifo_match:
        data['quantity'] = fifo_match.group(1)

    # Parse sale format: "Sale: 1 × 4 oz Jar for $15.00 ($15.00/unit) to Customer Name"
    sale_match = re.search(r'Sale:\s*([\d.]+)\s*×.*?for\s*\$?([\d.]+)', note)
    if sale_match:
        data['quantity'] = sale_match.group(1)
        data['sale_price'] = f"${sale_match.group(2)}"

    # Parse customer
    customer_match = re.search(r'to\s+(.+?)(?:\.|$)', note)
    if customer_match:
        data['customer'] = customer_match.group(1).strip()

    # If no structured data found, put everything in notes
    if not any([data['quantity'], data['sale_price'], data['customer']]):
        data['notes'] = note

    return data



def get_fifo_summary_helper(inventory_id):
    """Helper function to get FIFO summary for template"""
    try:
        return ProductService.get_fifo_summary(inventory_id)
    except:
        return None

@products_bp.route('/')
@login_required
def product_list():
    """List all products with inventory summary and sorting"""
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

    # Get units for dropdown

    units = get_global_unit_list()

    return render_template('products/new_product.html', units=units)

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with FIFO inventory"""

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

@products_bp.route('/<int:product_id>/deduct', methods=['POST'])
@login_required
def deduct_product(product_id):
    """Deduct product inventory using FIFO"""
    variant = request.form.get('variant', 'Base')
    unit = request.form.get('unit')
    quantity = float(request.form.get('quantity', 0))
    reason = request.form.get('reason', 'manual_deduction')
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    success = ProductService.deduct_fifo(
        product_id=product_id,
        variant_label=variant,
        unit=unit,
        quantity=quantity,
        reason=reason,
        notes=notes
    )

    if success:
        flash(f'Deducted {quantity} {unit} from {variant} using FIFO', 'success')
    else:
        flash('Not enough stock available', 'error')

    return redirect(url_for('products.view_product', product_id=product_id))

@products_bp.route('/<int:product_id>/adjust/<int:inventory_id>', methods=['POST'])


@products_bp.route('/api/<int:product_id>/variants', methods=['GET'])
@login_required
def get_product_variants(product_id):
    """API endpoint to get variants for a specific product"""
    product = Product.query.get_or_404(product_id)

    variants = []
    for variant in product.variations:
        variants.append({
            'id': variant.id,
            'name': variant.name,
            'sku': variant.sku
        })

    # Add default variant if no variants exist
    if not variants:
        variants.append({
            'id': None,
            'name': 'Default',
            'sku': None
        })

    return jsonify({'variants': variants})

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
            'default_unit': product.product_base_unit,
            'variants': []
        }

        # Add existing variants
        for variant in product.variations:
            product_data['variants'].append({
                'id': variant.id,
                'name': variant.name,
                'sku': variant.sku
            })

        # Add Base variant if no variants exist
        if not product.variations:
            product_data['variants'].append({
                'id': None,
                'name': 'Base',
                'sku': None
            })

        result.append(product_data)

    return jsonify({'products': result})

@products_bp.route('/api/add-from-batch', methods=['POST'])
@login_required
def add_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_id = data.get('product_id') 
    variant_label = data.get('variant_label')
    size_label = data.get('size_label')
    quantity = data.get('quantity')

    if not batch_id or not product_id:
        return jsonify({'error': 'Batch ID and Product ID are required'}), 400

    try:
        inventory = ProductService.add_product_from_batch(
            batch_id=batch_id,
            product_id=product_id,
            variant_label=variant_label,
            size_label=size_label,
            quantity=quantity
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'inventory_id': inventory.id,
            'message': f'Added {inventory.quantity} {inventory.unit} to product inventory'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@products_bp.route('/api/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """Quick add product and/or variant for finish batch modal"""
    data = request.get_json()

    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    product_base_unit = data.get('product_base_unit', 'oz')

    if not product_name:
        return jsonify({'error': 'Product name is required'}), 400

    # Check if product exists
    product = Product.query.filter_by(name=product_name).first()

    if not product:
        # Create new product
        product = Product(
            name=product_name,
            product_base_unit=product_base_unit
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
            'product_base_unit': product.product_base_unit
        },
        'variant': {
            'id': variant.id if variant else None,
            'name': variant.name if variant else 'Default'
        } if variant or variant_name else None
    })

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

@products_bp.route('/<int:product_id>/add-manual-stock', methods=['POST'])
@login_required
def add_manual_stock(product_id):
    """Add manual stock with container matching"""

    variant_name = request.form.get('variant_name')
    container_id = request.form.get('container_id')
    quantity = float(request.form.get('quantity', 0))
    unit_cost = float(request.form.get('unit_cost', 0))
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    try:
        inventory = ProductService.add_manual_stock(
            product_id=product_id,
            variant_name=variant_name,
            container_id=container_id,
            quantity=quantity,
            unit_cost=unit_cost,
            notes=notes
        )

        flash(f'Added {quantity} units to product inventory', 'success')
    except Exception as e:
        flash(f'Error adding stock: {str(e)}', 'error')

    return redirect(url_for('products.view_product', product_id=product_id))


@products_bp.route('/<int:product_id>/sku/<variant>/<size_label>')
@login_required  
def view_sku(product_id, variant, size_label):
    """View detailed SKU-level inventory with FIFO tracking"""
    from urllib.parse import unquote
    from models import ProductInventoryHistory

    product = Product.query.get_or_404(product_id)
    variant = unquote(variant)
    size_label = unquote(size_label)

    # Get all FIFO entries for this SKU combination
    fifo_entries = ProductInventory.query.filter_by(
        product_id=product_id,
        variant=variant,
        size_label=size_label
    ).order_by(ProductInventory.timestamp.asc()).all()

    # Calculate totals
    total_quantity = sum(entry.quantity for entry in fifo_entries if entry.quantity > 0)
    total_batches = len(set(entry.batch_id for entry in fifo_entries if entry.batch_id))

    # Get recent deductions/sales from product events
    recent_deductions = ProductEvent.query.filter(
        ProductEvent.product_id == product_id,
        ProductEvent.note.like(f'%{variant}%'),
        ProductEvent.note.like(f'%{size_label}%')
    ).order_by(ProductEvent.timestamp.desc()).limit(20).all()

    return render_template('products/view_sku.html',
                         product=product,
                         variant=variant,
                         size_label=size_label,
                         fifo_entries=fifo_entries,
                         total_quantity=total_quantity,
                         total_batches=total_batches,
                         recent_deductions=recent_deductions,
                         moment=datetime)

@products_bp.route('/<int:product_id>/record_sale', methods=['POST'])
@login_required
def record_sale(product_id):
    """Record a sale or other inventory adjustment using unified ProductService"""
    variant = request.form.get('variant')
    size_label = request.form.get('size_label') 
    quantity = float(request.form.get('quantity'))
    reason = request.form.get('reason', 'sale')
    notes = request.form.get('notes', '')
    sale_price = request.form.get('sale_price')
    customer = request.form.get('customer')
    unit_cost = request.form.get('unit_cost')

    try:
        from services.product_service import ProductService

        success = ProductService.process_inventory_adjustment(
            product_id=product_id,
            variant=variant,
            size_label=size_label,
            adjustment_type=reason,
            quantity=quantity,
            notes=notes,
            sale_price=float(sale_price) if sale_price else None,
            customer=customer,
            unit_cost=float(unit_cost) if unit_cost else None
        )

        if success:
            flash(f"✅ {reason.replace('_', ' ').title()} recorded successfully!", "success")
        else:
            flash("❌ Insufficient stock for this operation", "error")

    except Exception as e:
        flash(f"❌ Error: {str(e)}", "error")

    return redirect(request.referrer or url_for('products.view_product', product_id=product_id))

@products_bp.route('/<int:product_id>/manual-adjust', methods=['POST'])
@login_required
def manual_adjust(product_id):
    """Manual inventory adjustments for variant/size"""
    variant = request.form.get('variant', 'Base')
    size_label = request.form.get('size_label')
    adjustment_type = request.form.get('adjustment_type')
    quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    # Implementation would depend on adjustment type
    # This is a placeholder for the manual adjustment logic

    flash(f'Manual adjustment applied: {adjustment_type}', 'success')
    return redirect(url_for('products.view_sku', 
                           product_id=product_id, variant=variant, size_label=size_label))



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
        variant=variation.name
    ).order_by(ProductInventory.timestamp.asc()).all()

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
        ProductEvent.note.like(f'%{variation.name}%')
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

@products_bp.route('/<int:product_id>/sku/<variant>/<size_label>/edit', methods=['POST'])
@login_required
def edit_sku(product_id, variant, size_label):
    """Edit SKU for a specific product variant and size"""
    from urllib.parse import unquote

    product = Product.query.get_or_404(product_id)
    variant = unquote(variant)
    size_label = unquote(size_label)

    sku = request.form.get('sku', '').strip()

    # Update all ProductInventory entries for this variant/size combination
    inventory_entries = ProductInventory.query.filter_by(
        product_id=product_id,
        variant=variant,
        size_label=size_label
    ).all()

    if not inventory_entries:
        flash('No inventory entries found for this variant/size combination', 'error')
        return redirect(url_for('products.view_sku', 
                               product_id=product_id, variant=variant, size_label=size_label))

    # Check if SKU already exists for another product/variant/size combination
    if sku:
        existing_sku = ProductInventory.query.filter(
            ProductInventory.sku == sku,
            db.or_(
                ProductInventory.product_id != product_id,
                ProductInventory.variant != variant,
                ProductInventory.size_label != size_label
            )
        ).first()

        if existing_sku:
            flash(f'SKU "{sku}" is already in use for another product/variant/size', 'error')
            return redirect(url_for('products.view_sku', 
                                   product_id=product_id, variant=variant, size_label=size_label))

    # Update all entries
    for entry in inventory_entries:
        entry.sku = sku if sku else None

    db.session.commit()

    if sku:
        flash(f'SKU updated to "{sku}" for {variant} - {size_label}', 'success')
    else:
        flash(f'SKU removed for {variant} - {size_label}', 'success')

    return redirect(url_for('products.view_sku', 
                           product_id=product_id, variant=variant, size_label=size_label))

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

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product and all its related data"""
    product = Product.query.get_or_404(product_id)

    try:
        # Check if product has any batches
        if product.batches:
            flash('Cannot delete product with associated batches', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        # Delete related records in order
        # Delete product inventory history

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

@products_bp.route('/adjust_fifo/<int:product_id>/<int:inventory_id>', methods=['POST'])
@login_required
def adjust_fifo_inventory(product_id, inventory_id):
    """Adjust the quantity of a specific FIFO entry."""
    adjustment_type = request.form.get('adjustment_type')  # recount, sale, spoil, damage, trash, gift/tester
    quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('products.view_sku', product_id=product_id, variant=request.form.get('variant'), size_label=request.form.get('size_label')))

    try:
        adjust_product_fifo_entry(
            inventory_id=inventory_id,
            adjustment_type=adjustment_type,
            quantity=quantity,
            notes=notes
        )

        flash(f'FIFO entry adjusted: {adjustment_type}', 'success')

    except Exception as e:
        flash(f'Error adjusting FIFO entry: {str(e)}', 'error')

    # Redirect back to the SKU view. Crucial to pass variant and size_label.
    return redirect(url_for('products.view_sku', product_id=product_id, variant=request.form.get('variant'), size_label=request.form.get('size_label')))