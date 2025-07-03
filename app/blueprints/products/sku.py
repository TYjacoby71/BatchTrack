
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, ProductSKU, ProductSKUHistory
from ...utils.unit_utils import get_global_unit_list
from . import products_bp

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

@products_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku(sku_id):
    """Adjust SKU inventory - should be moved to product inventory system"""
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
