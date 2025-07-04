
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, ProductSKU, ProductSKUHistory
from ...utils.unit_utils import get_global_unit_list

# Create the sku blueprint
sku_bp = Blueprint('sku', __name__)

@sku_bp.route('/sku/<int:sku_id>')
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

@sku_bp.route('/sku/<int:sku_id>/edit', methods=['POST'])
@login_required
def edit_sku(sku_id):
    """Edit SKU details"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first_or_404()
    
    try:
        # Update basic fields
        sku.sku_code = request.form.get('sku_code')
        sku.size_label = request.form.get('size_label')
        sku.location_name = request.form.get('location_name')
        
        # Update pricing
        retail_price = request.form.get('retail_price')
        if retail_price:
            sku.retail_price = float(retail_price)
        
        # Update thresholds
        low_stock_threshold = request.form.get('low_stock_threshold')
        if low_stock_threshold:
            sku.low_stock_threshold = float(low_stock_threshold)
        
        # Handle unit cost override
        if request.form.get('override_unit_cost'):
            unit_cost = request.form.get('unit_cost')
            if unit_cost and sku.inventory_item:
                # Update the underlying inventory item cost
                sku.inventory_item.cost_per_unit = float(unit_cost)
                # Also update SKU unit_cost for compatibility
                sku.unit_cost = float(unit_cost)
        
        # Handle perishable settings
        sku.is_perishable = bool(request.form.get('is_perishable'))
        if sku.is_perishable:
            shelf_life_days = request.form.get('shelf_life_days')
            if shelf_life_days:
                sku.shelf_life_days = int(shelf_life_days)
        else:
            sku.shelf_life_days = None
        
        # Handle recount if provided
        recount_quantity = request.form.get('recount_quantity')
        if recount_quantity:
            from ...services.inventory_adjustment import process_inventory_adjustment
            recount_notes = request.form.get('recount_notes', 'Inventory recount from SKU edit')
            
            try:
                success = process_inventory_adjustment(
                    item_id=sku.inventory_item_id,
                    quantity=float(recount_quantity),
                    change_type='recount',
                    unit=sku.unit,
                    notes=recount_notes,
                    created_by=current_user.id,
                    item_type='product'
                )
                
                if success:
                    flash('SKU updated and inventory recounted successfully', 'success')
                else:
                    flash('SKU updated but recount failed', 'warning')
            except Exception as e:
                flash(f'SKU updated but recount error: {str(e)}', 'warning')
        else:
            flash('SKU updated successfully', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating SKU: {str(e)}', 'error')
    
    return redirect(url_for('sku.view_sku', sku_id=sku_id))

@sku_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku(sku_id):
    """Legacy route - redirect to consolidated product inventory adjustment"""
    # Redirect to the consolidated product inventory adjustment route
    from .product_inventory_routes import adjust_sku_inventory
    return adjust_sku_inventory(sku_id)
