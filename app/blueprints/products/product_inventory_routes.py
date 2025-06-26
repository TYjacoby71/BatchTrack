from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from urllib.parse import unquote

from ...models import db, ProductSKU
from ...services.product_inventory_service import ProductInventoryService

product_inventory_bp = Blueprint('product_inventory', __name__)

@product_inventory_bp.route('/sku/<int:sku_id>')
@login_required  
def view_sku(sku_id):
    """View detailed SKU-level inventory - the point of truth"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    fifo_filter = request.args.get('fifo') == 'true'

    sku = ProductSKU.query.get_or_404(sku_id)

    # Get FIFO entries
    fifo_entries = ProductInventoryService.get_fifo_entries(sku_id, active_only=fifo_filter)

    # Get history with pagination
    history_data = ProductInventoryService.get_sku_history(sku_id, page, per_page)

    # Calculate totals
    total_quantity = sku.current_quantity
    total_batches = len(set(entry.batch_id for entry in fifo_entries if entry.batch_id))

    # Create a mock product object for template compatibility
    class MockProduct:
        def __init__(self, sku):
            self.id = sku.id
            self.name = sku.product_name
    
    product = MockProduct(sku)
    variant = sku.variant_name
    size_label = sku.size_label
    
    return render_template('products/view_sku.html',
                         sku=sku,
                         product=product,
                         variant=variant,
                         size_label=size_label,
                         fifo_entries=fifo_entries,
                         history=history_data['items'],
                         history_pagination=history_data['pagination'],
                         total_quantity=total_quantity,
                         total_batches=total_batches,
                         fifo_filter=fifo_filter)

@product_inventory_bp.route('/sku/<int:sku_id>/edit', methods=['POST'])
@login_required
def edit_sku_code(sku_id):
    """Edit SKU code"""
    sku = ProductSKU.query.get_or_404(sku_id)

    sku_code = request.form.get('sku_code', '').strip()

    # Check if SKU code already exists
    if sku_code:
        existing = ProductSKU.query.filter(
            ProductSKU.sku_code == sku_code,
            ProductSKU.id != sku_id
        ).first()

        if existing:
            flash(f'SKU code "{sku_code}" is already in use', 'error')
            return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

    sku.sku_code = sku_code if sku_code else None
    db.session.commit()

    if sku_code:
        flash(f'SKU code updated to "{sku_code}"', 'success')
    else:
        flash('SKU code removed', 'success')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/sku/<int:sku_id>/add_stock', methods=['POST'])
@login_required
def add_stock(sku_id):
    """Add manual stock to SKU"""
    quantity = float(request.form.get('quantity', 0))
    unit_cost = float(request.form.get('unit_cost', 0))
    notes = request.form.get('notes', '')
    container_id = request.form.get('container_id')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

    try:
        ProductInventoryService.add_stock(
            sku_id=sku_id,
            quantity=quantity,
            unit_cost=unit_cost,
            container_id=int(container_id) if container_id else None,
            notes=notes,
            change_type='manual_addition'
        )
        db.session.commit()
        flash(f'Added {quantity} units to SKU', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding stock: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/sku/<int:sku_id>/deduct', methods=['POST'])
@login_required
def deduct_stock(sku_id):
    """Deduct stock from SKU"""
    quantity = float(request.form.get('quantity', 0))
    change_type = request.form.get('change_type', 'manual_deduction')
    notes = request.form.get('notes', '')
    sale_price = request.form.get('sale_price')
    customer = request.form.get('customer')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

    try:
        success = ProductInventoryService.deduct_stock(
            sku_id=sku_id,
            quantity=quantity,
            change_type=change_type,
            sale_price=float(sale_price) if sale_price else None,
            customer=customer,
            notes=notes
        )

        if success:
            db.session.commit()
            flash(f'{change_type.replace("_", " ").title()} recorded successfully', 'success')
        else:
            db.session.rollback()
            flash('Insufficient stock available', 'error')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/sku/<int:sku_id>/recount', methods=['POST'])
@login_required
def recount_sku(sku_id):
    """Recount SKU inventory"""
    new_quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    try:
        success = ProductInventoryService.recount_sku(sku_id, new_quantity, notes)

        if success:
            db.session.commit()
            flash('Inventory recount completed successfully', 'success')
        else:
            db.session.rollback()
            flash('Failed to process recount', 'error')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/sku/<int:sku_id>/deduct', methods=['POST'])
@login_required
def recount_stock(sku_id):
    """Recount SKU stock"""
    new_total = float(request.form.get('new_total', 0))
    notes = request.form.get('notes', '')

    try:
        success = ProductInventoryService.recount_stock(
            sku_id=sku_id,
            new_total=new_total,
            notes=notes
        )

        if success:
            db.session.commit()
            flash('Recount completed successfully', 'success')
        else:
            flash('Error during recount', 'error')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/fifo/<int:inventory_id>/adjust', methods=['POST'])
@login_required
def adjust_fifo_entry(inventory_id):
    """Adjust specific FIFO entry"""
    change_type = request.form.get('change_type')
    quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(request.referrer)

    try:
        success = ProductInventoryService.adjust_fifo_entry(
            inventory_id=inventory_id,
            quantity=quantity,
            change_type=change_type,
            notes=notes
        )

        if success:
            db.session.commit()
            flash('FIFO entry adjusted successfully', 'success')
        else:
            db.session.rollback()
            flash('Error adjusting FIFO entry', 'error')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(request.referrer)

@product_inventory_bp.route('/api/sku_summary')
@login_required
def sku_summary_api():
    """API endpoint for SKU summary data"""
    try:
        summary = ProductInventoryService.get_all_skus_summary()
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Legacy route compatibility  
@product_inventory_bp.route('/<int:product_id>/sku/<variant>/<size_label>')
@login_required  
def view_sku_legacy(product_id, variant, size_label):
    """Legacy route - redirect to new SKU-based route"""
    variant = unquote(variant)
    size_label = unquote(size_label)

    # Find the SKU by name (since we don't have product_id anymore)
    sku = ProductSKU.query.filter_by(
        variant_name=variant,
        size_label=size_label
    ).first()

    if not sku:
        flash('SKU not found', 'error')
        return redirect(url_for('dashboard.index'))

    return redirect(url_for('product_inventory.view_sku', sku_id=sku.id))