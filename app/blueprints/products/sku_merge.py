
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from datetime import datetime
from ...models import db, ProductSKU, ProductSKUHistory, InventoryItem, Reservation
from ...services.inventory_adjustment import process_inventory_adjustment
import logging

logger = logging.getLogger(__name__)

sku_merge_bp = Blueprint('sku_merge', __name__)

@sku_merge_bp.route('/merge/select')
@login_required
def select_skus_to_merge():
    """Select SKUs to merge - show all active SKUs"""
    skus = ProductSKU.query.join(InventoryItem).filter(
        ProductSKU.organization_id == current_user.organization_id,
        ProductSKU.is_active == True
    ).order_by(ProductSKU.product_id, ProductSKU.variant_id, ProductSKU.size_label).all()
    
    return render_template('products/merge_select.html', skus=skus)

@sku_merge_bp.route('/merge/configure', methods=['POST'])
@login_required
def configure_merge():
    """Configure merge settings for selected SKUs"""
    sku_ids = request.form.getlist('sku_ids')
    
    if len(sku_ids) < 2:
        flash('Please select at least 2 SKUs to merge', 'error')
        return redirect(url_for('sku_merge.select_skus_to_merge'))
    
    # Get selected SKUs
    skus = ProductSKU.query.filter(
        ProductSKU.inventory_item_id.in_(sku_ids),
        ProductSKU.organization_id == current_user.organization_id
    ).all()
    
    # Validate all SKUs have same product and variant
    if len(set((sku.product_id, sku.variant_id) for sku in skus)) > 1:
        flash('Can only merge SKUs of the same product and variant', 'error')
        return redirect(url_for('sku_merge.select_skus_to_merge'))
    
    # Validate all SKUs have same unit
    if len(set(sku.unit for sku in skus)) > 1:
        flash('Can only merge SKUs with the same unit', 'error')
        return redirect(url_for('sku_merge.select_skus_to_merge'))
    
    # Get merge configuration data
    merge_config = {
        'skus': skus,
        'attributes': [
            {'key': 'size_label', 'label': 'Size Label', 'type': 'text'},
            {'key': 'sku_code', 'label': 'SKU Code', 'type': 'text'},
            {'key': 'sku_name', 'label': 'SKU Name', 'type': 'text'},
            {'key': 'retail_price', 'label': 'Retail Price', 'type': 'number'},
            {'key': 'wholesale_price', 'label': 'Wholesale Price', 'type': 'number'},
            {'key': 'low_stock_threshold', 'label': 'Low Stock Threshold', 'type': 'number'},
            {'key': 'category', 'label': 'Category', 'type': 'text'},
            {'key': 'subcategory', 'label': 'Subcategory', 'type': 'text'},
            {'key': 'description', 'label': 'Description', 'type': 'textarea'},
            {'key': 'location_name', 'label': 'Location', 'type': 'text'},
            {'key': 'barcode', 'label': 'Barcode', 'type': 'text'},
            {'key': 'is_perishable', 'label': 'Perishable', 'type': 'boolean'},
            {'key': 'shelf_life_days', 'label': 'Shelf Life (Days)', 'type': 'number'},
        ]
    }
    
    return render_template('products/merge_configure.html', **merge_config)

@sku_merge_bp.route('/merge/execute', methods=['POST'])
@login_required
def execute_merge():
    """Execute the SKU merge"""
    try:
        sku_ids = request.form.getlist('sku_ids')
        target_sku_id = request.form.get('target_sku_id')
        
        if not target_sku_id or target_sku_id not in sku_ids:
            flash('Invalid target SKU selected', 'error')
            return redirect(url_for('sku_merge.select_skus_to_merge'))
        
        # Get all SKUs
        skus = ProductSKU.query.filter(
            ProductSKU.inventory_item_id.in_(sku_ids),
            ProductSKU.organization_id == current_user.organization_id
        ).all()
        
        target_sku = next((sku for sku in skus if str(sku.inventory_item_id) == target_sku_id), None)
        source_skus = [sku for sku in skus if str(sku.inventory_item_id) != target_sku_id]
        
        if not target_sku:
            flash('Target SKU not found', 'error')
            return redirect(url_for('sku_merge.select_skus_to_merge'))
        
        # Update target SKU attributes based on form selections
        for attr in ['size_label', 'sku_code', 'sku_name', 'retail_price', 'wholesale_price', 
                     'low_stock_threshold', 'category', 'subcategory', 'description', 
                     'location_name', 'barcode', 'shelf_life_days']:
            selected_sku_id = request.form.get(f'attr_{attr}')
            if selected_sku_id:
                source_sku = next((sku for sku in skus if str(sku.inventory_item_id) == selected_sku_id), None)
                if source_sku:
                    value = getattr(source_sku, attr)
                    if value is not None:
                        setattr(target_sku, attr, value)
        
        # Handle boolean attributes
        is_perishable_sku_id = request.form.get('attr_is_perishable')
        if is_perishable_sku_id:
            source_sku = next((sku for sku in skus if str(sku.inventory_item_id) == is_perishable_sku_id), None)
            if source_sku:
                target_sku.is_perishable = source_sku.is_perishable
        
        # Merge inventory quantities
        total_quantity = sum(sku.quantity for sku in skus)
        target_sku.inventory_item.quantity = total_quantity
        
        # Calculate weighted average cost
        total_value = sum(sku.quantity * (sku.cost_per_unit or 0) for sku in skus)
        if total_quantity > 0:
            target_sku.inventory_item.cost_per_unit = total_value / total_quantity
        
        # Merge history entries
        for source_sku in source_skus:
            # Update all history entries to point to target SKU
            ProductSKUHistory.query.filter_by(
                inventory_item_id=source_sku.inventory_item_id
            ).update({'inventory_item_id': target_sku.inventory_item_id})
            
            # Update reservations
            Reservation.query.filter_by(
                product_item_id=source_sku.inventory_item_id
            ).update({'product_item_id': target_sku.inventory_item_id})
        
        # Create merge record in history
        merge_note = f"Merged SKUs: {', '.join(sku.sku_code for sku in source_skus)} into {target_sku.sku_code}"
        
        # Add adjustment record for the merge
        process_inventory_adjustment(
            item_id=target_sku.inventory_item_id,
            quantity=0,  # No quantity change, just record the merge
            change_type='sku_merge',
            unit=target_sku.unit,
            notes=merge_note,
            created_by=current_user.id
        )
        
        # Delete source SKUs and their inventory items
        for source_sku in source_skus:
            db.session.delete(source_sku.inventory_item)
            db.session.delete(source_sku)
        
        # Update target SKU timestamp
        target_sku.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Successfully merged {len(source_skus)} SKUs into {target_sku.sku_code}', 'success')
        return redirect(url_for('sku.view_sku', inventory_item_id=target_sku.inventory_item_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error merging SKUs: {str(e)}")
        flash(f'Error merging SKUs: {str(e)}', 'error')
        return redirect(url_for('sku_merge.select_skus_to_merge'))

@sku_merge_bp.route('/api/sku/<int:sku_id>/merge_preview')
@login_required
def get_merge_preview(sku_id):
    """Get preview data for SKU merge"""
    sku = ProductSKU.query.filter_by(
        inventory_item_id=sku_id,
        organization_id=current_user.organization_id
    ).first_or_404()
    
    # Get history count
    history_count = ProductSKUHistory.query.filter_by(
        inventory_item_id=sku_id
    ).count()
    
    # Get reservations count
    reservations_count = Reservation.query.filter_by(
        product_item_id=sku_id,
        status='active'
    ).count()
    
    return jsonify({
        'sku_code': sku.sku_code,
        'quantity': sku.quantity,
        'cost_per_unit': sku.cost_per_unit,
        'history_count': history_count,
        'reservations_count': reservations_count
    })
