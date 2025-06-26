from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from urllib.parse import unquote

from ...models import db, ProductSKU
from ...services.product_inventory_service import ProductInventoryService
from ...utils.unit_utils import get_global_unit_list
from datetime import datetime

product_inventory_bp = Blueprint('product_inventory', __name__)

@product_inventory_bp.route('/sku/<int:sku_id>', methods=['GET', 'POST'])
@login_required  
def view_sku(sku_id):
    """View detailed SKU-level inventory - the point of truth"""
    if request.method == 'POST':
        # Pre-validation check for SKU/FIFO sync
        is_valid, error_msg, sku_qty, fifo_total = ProductInventoryService.validate_sku_fifo_sync(sku_id)
        if not is_valid:
            flash(f'Pre-adjustment validation failed: {error_msg}', 'error')
            return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

        # Handle standard inventory adjustment
        change_type = request.form.get('change_type')
        quantity = float(request.form.get('quantity', 0))
        notes = request.form.get('notes', '')
        sale_price = request.form.get('sale_price', 0, type=float)
        customer = request.form.get('customer', '')
        unit_cost = request.form.get('unit_cost', 0, type=float)
        enhanced_notes = {
            'user_notes': notes,
            'sale_price': sale_price,
            'customer': customer,
            'unit_cost': unit_cost
        }

        if quantity <= 0:
            flash('Quantity must be positive', 'error')
            return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

        try:
            if change_type == 'recount':
                success = ProductInventoryService.recount_sku(sku_id, quantity, enhanced_notes)
            elif change_type in ['sale', 'gift', 'spoil', 'damaged', 'trash', 'sample']:
                success = ProductInventoryService.deduct_stock(
                    sku_id=sku_id,
                    quantity=quantity,
                    change_type=change_type,
                    notes=enhanced_notes,
                    sale_price=sale_price,
                    customer=customer
                )
            else:  # restock, adjustment, return, manual_addition
                ProductInventoryService.add_stock(
                    sku_id=sku_id,
                    quantity=quantity,
                    unit_cost=unit_cost or 0,
                    change_type=change_type,
                    notes=enhanced_notes,
                    sale_price=sale_price,
                    customer=customer
                )
                success = True

            if success:
                # Post-validation check for SKU/FIFO sync
                is_valid_post, error_msg_post, sku_qty_post, fifo_total_post = ProductInventoryService.validate_sku_fifo_sync(sku_id)
                if not is_valid_post:
                    db.session.rollback()
                    flash(f'Post-adjustment validation failed: {error_msg_post}', 'error')
                    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

                db.session.commit()
                action_name = change_type.replace('_', ' ').title()
                if customer:
                    flash(f'{action_name} for {customer} recorded successfully', 'success')
                else:
                    flash(f'{action_name} recorded successfully', 'success')
            else:
                db.session.rollback()
                flash('Insufficient stock for this transaction', 'error')

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

        return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

    # GET request handling
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

    context = {
        'sku': sku,
        'total_quantity': total_quantity,
        'history': history_data['items'],
        'history_pagination': history_data['pagination'],
        'total_batches': total_batches,
        'fifo_filter': fifo_filter,
        'get_global_unit_list': get_global_unit_list
    }

    return render_template('products/view_sku.html', **context)


@product_inventory_bp.route('/sku/<int:sku_id>/edit', methods=['POST'])
@login_required
def edit_sku(sku_id):
    """Edit SKU details"""
    sku = ProductSKU.query.get_or_404(sku_id)

    # Pre-validation check for SKU/FIFO sync
    is_valid, error_msg, sku_qty, fifo_total = ProductInventoryService.validate_sku_fifo_sync(sku_id)
    if not is_valid:
        flash(f'Pre-edit validation failed: {error_msg}', 'error')
        return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

    try:
        # Update basic fields
        sku.sku_code = request.form.get('sku_code').strip() if request.form.get('sku_code') else None
        sku.size_label = request.form.get('size_label').strip()
        sku.retail_price = float(request.form.get('retail_price')) if request.form.get('retail_price') else None
        sku.low_stock_threshold = float(request.form.get('low_stock_threshold', 0))
        sku.unit = request.form.get('unit')
        sku.is_active = bool(request.form.get('is_active'))
        sku.track_expiration = bool(request.form.get('track_expiration'))
        sku.description = request.form.get('description').strip() if request.form.get('description') else None
        sku.barcode = request.form.get('barcode').strip() if request.form.get('barcode') else None

        # Handle unit cost override
        override_unit_cost = bool(request.form.get('override_unit_cost'))
        if override_unit_cost:
            new_unit_cost = request.form.get('unit_cost')
            if new_unit_cost:
                sku.unit_cost = float(new_unit_cost)

        # Auto-generate SKU code if not provided
        if not sku.sku_code:
            sku.sku_code = f"{sku.product_name}-{sku.variant_name}-{sku.size_label}".replace(' ', '-').upper()

        sku.last_updated = datetime.utcnow()
        
        # Post-validation check for SKU/FIFO sync (in case unit changes affected calculations)
        is_valid_post, error_msg_post, sku_qty_post, fifo_total_post = ProductInventoryService.validate_sku_fifo_sync(sku_id)
        if not is_valid_post:
            db.session.rollback()
            flash(f'Post-edit validation failed: {error_msg_post}', 'error')
            return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

        db.session.commit()
        flash('SKU details updated successfully!', 'success')

    except ValueError as e:
        db.session.rollback()
        flash(f'Invalid input: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating SKU: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/adjust_fifo/<int:history_id>', methods=['POST'])
@login_required
def adjust_fifo_entry(history_id):
    """Adjust specific FIFO entry"""
    change_type = request.form.get('change_type')
    quantity = float(request.form.get('quantity', 0))
    notes = request.form.get('notes', '')

    if quantity <= 0:
        flash('Quantity must be positive', 'error')
        return redirect(request.referrer)

    # Get the SKU ID for validation
    from ...models import ProductSKUHistory
    history_entry = ProductSKUHistory.query.get_or_404(history_id)
    sku_id = history_entry.sku_id

    # Pre-validation check for SKU/FIFO sync
    is_valid, error_msg, sku_qty, fifo_total = ProductInventoryService.validate_sku_fifo_sync(sku_id)
    if not is_valid:
        flash(f'Pre-adjustment validation failed: {error_msg}', 'error')
        return redirect(request.referrer)

    try:
        success = ProductInventoryService.adjust_fifo_entry(
            history_id=history_id,
            quantity=quantity,
            change_type=change_type,
            notes=notes
        )

        if success:
            # Post-validation check for SKU/FIFO sync
            is_valid_post, error_msg_post, sku_qty_post, fifo_total_post = ProductInventoryService.validate_sku_fifo_sync(sku_id)
            if not is_valid_post:
                db.session.rollback()
                flash(f'Post-adjustment validation failed: {error_msg_post}', 'error')
                return redirect(request.referrer)

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