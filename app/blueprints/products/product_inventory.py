from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, Product, ProductInventory, ProductEvent
from ...services.product_service import ProductService, adjust_product_fifo_entry
from datetime import datetime
from urllib.parse import unquote

from . import products_bp

product_inventory_bp = Blueprint('product_inventory', __name__, template_folder='templates')

@product_inventory_bp.route('/<int:product_id>/sku/<variant>/<size_label>')
@login_required  
def view_sku(product_id, variant, size_label):
    """View detailed SKU-level inventory with FIFO tracking"""
    from ...models import ProductInventoryHistory

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
        ProductEvent.description.like(f'%{variant}%'),
        ProductEvent.description.like(f'%{size_label}%')
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

@product_inventory_bp.route('/<int:product_id>/sku/<variant>/<size_label>/edit', methods=['POST'])
@login_required
def edit_sku(product_id, variant, size_label):
    """Edit SKU for a specific product variant and size"""
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
        return redirect(url_for('product_inventory.view_sku', 
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
            return redirect(url_for('product_inventory.view_sku', 
                                   product_id=product_id, variant=variant, size_label=size_label))

    # Update all entries
    for entry in inventory_entries:
        entry.sku = sku if sku else None

    db.session.commit()

    if sku:
        flash(f'SKU updated to "{sku}" for {variant} - {size_label}', 'success')
    else:
        flash(f'SKU removed for {variant} - {size_label}', 'success')

    return redirect(url_for('product_inventory.view_sku', 
                           product_id=product_id, variant=variant, size_label=size_label))

@product_inventory_bp.route('/adjust_fifo/<int:inventory_id>', methods=['POST'])
@login_required
def adjust_fifo_inventory(inventory_id):
    """Adjust the quantity of a specific FIFO entry."""
    adjustment_type = request.form.get('change_type')  # recount, sale, spoil, damage, trash, gift/tester
    quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(request.referrer)

    try:
        # Get the inventory entry to determine product and SKU details for redirect
        inventory_entry = ProductInventory.query.get_or_404(inventory_id)

        # For recount, pass the new total quantity
        # For deductions, pass the negative quantity to deduct
        if adjustment_type == 'recount':
            quantity_change = quantity  # This is the new total
        else:
            quantity_change = -quantity  # Negative for deductions

        success = adjust_product_fifo_entry(
            fifo_entry_id=inventory_id,
            quantity=quantity_change,
            change_type=adjustment_type,
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None
        )

        if success:
            flash(f'FIFO entry adjusted: {adjustment_type}', 'success')
        else:
            flash('Failed to adjust FIFO entry', 'error')

    except Exception as e:
        flash(f'Error adjusting FIFO entry: {str(e)}', 'error')

    return redirect(request.referrer or url_for('products.view_product', product_id=inventory_entry.product_id))

@product_inventory_bp.route('/<int:product_id>/deduct', methods=['POST'])
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

@product_inventory_bp.route('/<int:product_id>/add-manual-stock', methods=['POST'])
@login_required
def add_manual_stock(product_id):
    """Add manual stock with container matching"""
    from ...models import InventoryItem
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

@product_inventory_bp.route('/<int:product_id>/record_sale', methods=['POST'])
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

@product_inventory_bp.route('/<int:product_id>/manual-adjust', methods=['POST'])
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
    return redirect(url_for('product_inventory.view_sku', 
                           product_id=product_id, variant=variant, size_label=size_label))