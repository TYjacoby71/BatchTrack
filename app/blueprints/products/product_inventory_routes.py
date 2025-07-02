from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from urllib.parse import unquote

from ...models import db, ProductSKU, ProductSKUHistory
from ...services.product_inventory_service import ProductInventoryService
from ...utils.unit_utils import get_global_unit_list
from datetime import datetime

product_inventory_bp = Blueprint('product_inventory', __name__)

@product_inventory_bp.route('/sku/<int:sku_id>', methods=['GET', 'POST'])
@login_required  
def view_sku(sku_id):
    """View detailed SKU-level inventory - the point of truth"""
    if request.method == 'POST':
        # Handle standard inventory adjustment
        change_type = request.form.get('change_type')
        
        # Safe float parsing
        try:
            quantity = float(request.form.get('quantity', '0'))
        except ValueError:
            quantity = 0
            
        try:
            sale_price = float(request.form.get('sale_price', '0'))
        except ValueError:
            sale_price = 0
            
        try:
            unit_cost = float(request.form.get('unit_cost', '0'))
        except ValueError:
            unit_cost = 0
            
        notes = request.form.get('notes', '')
        customer = request.form.get('customer', '')
        # Convert to string format that the service expects
        enhanced_notes = f"User notes: {notes}, Sale price: {sale_price}, Customer: {customer}, Unit cost: {unit_cost}"

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


@product_inventory_bp.route('/sku/<int:sku_id>/edit_basic', methods=['POST'])
@login_required
def edit_sku_basic(sku_id):
    """Edit basic SKU details"""
    sku = ProductSKU.query.get_or_404(sku_id)

    try:
        # Update basic fields with safe string handling
        sku_code = request.form.get('sku_code', '').strip()
        sku.sku_code = sku_code if sku_code else None
        
        size_label = request.form.get('size_label', '').strip()
        sku.size_label = size_label if size_label else sku.size_label
        
        # Safe float parsing
        try:
            retail_price_str = request.form.get('retail_price', '').strip()
            sku.retail_price = float(retail_price_str) if retail_price_str else None
        except ValueError:
            sku.retail_price = None
            
        try:
            threshold_str = request.form.get('low_stock_threshold', '0').strip()
            sku.low_stock_threshold = float(threshold_str) if threshold_str else 0
        except ValueError:
            sku.low_stock_threshold = 0

        sku.unit = request.form.get('unit') or sku.unit
        sku.is_active = bool(request.form.get('is_active'))
        sku.track_expiration = bool(request.form.get('track_expiration'))
        
        description = request.form.get('description', '').strip()
        sku.description = description if description else None
        
        barcode = request.form.get('barcode', '').strip()
        sku.barcode = barcode if barcode else None

        # Handle unit cost override
        override_unit_cost = bool(request.form.get('override_unit_cost'))
        if override_unit_cost:
            try:
                unit_cost_str = request.form.get('unit_cost', '').strip()
                if unit_cost_str:
                    sku.unit_cost = float(unit_cost_str)
            except ValueError:
                flash('Invalid unit cost value', 'warning')

        # Auto-generate SKU code if not provided
        if not sku.sku_code:
            sku.sku_code = f"{sku.product_name}-{sku.variant_name}-{sku.size_label}".replace(' ', '-').upper()

        sku.last_updated = datetime.utcnow()
        db.session.commit()

        flash('SKU details updated successfully!', 'success')

    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating SKU: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/fifo/<int:inventory_id>/adjust', methods=['POST'])
@login_required
def adjust_fifo_entry(inventory_id):
    """Adjust specific FIFO entry"""
    change_type = request.form.get('change_type')
    
    # Safe float parsing
    try:
        quantity = float(request.form.get('quantity', '0'))
    except ValueError:
        quantity = 0
        
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

@product_inventory_bp.route('/sku/<int:sku_id>/process_adjustment', methods=['POST'])
@login_required
def process_inventory_adjustment(sku_id):
    """Process inventory adjustment for a specific SKU"""
    try:
        sku = ProductSKU.query.get_or_404(sku_id)
        return ProductInventoryService.process_inventory_adjustment(sku, request.form)
    except Exception as e:
        app.logger.error(f"Error processing inventory adjustment: {e}")
        flash(f'Error processing adjustment: {str(e)}', 'error')
        return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/sku/<int:sku_id>/edit', methods=['POST'])
@login_required
def edit_sku_details(sku_id):
    """Edit SKU details like retail price, SKU code, shelf life, etc."""
    sku = ProductSKU.query.get_or_404(sku_id)

    try:
        # Update basic fields
        sku.sku_code = request.form.get('sku_code') or None
        sku.size_label = request.form.get('size_label') or sku.size_label
        sku.location_name = request.form.get('location_name') or None

        # Handle retail price with safe parsing
        try:
            retail_price_str = request.form.get('retail_price', '').strip()
            sku.retail_price = float(retail_price_str) if retail_price_str else None
        except ValueError:
            sku.retail_price = None

        # Handle low stock threshold with safe parsing
        try:
            low_stock_str = request.form.get('low_stock_threshold', '0').strip()
            sku.low_stock_threshold = float(low_stock_str) if low_stock_str else 0
        except ValueError:
            sku.low_stock_threshold = 0

        # Handle unit cost override with safe parsing
        if request.form.get('override_unit_cost'):
            try:
                unit_cost_str = request.form.get('unit_cost', '').strip()
                if unit_cost_str:
                    sku.unit_cost = float(unit_cost_str)
            except ValueError:
                flash('Invalid unit cost value', 'warning')

        # Handle shelf life management
        is_perishable = request.form.get('is_perishable') == 'on'
        sku.is_perishable = is_perishable

        if is_perishable:
            try:
                shelf_life_str = request.form.get('shelf_life_days', '').strip()
                if shelf_life_str:
                    old_shelf_life = sku.shelf_life_days
                    sku.shelf_life_days = int(shelf_life_str)
                else:
                    old_shelf_life = sku.shelf_life_days
                    sku.shelf_life_days = None
            except ValueError:
                flash('Invalid shelf life value', 'warning')
                old_shelf_life = sku.shelf_life_days
                sku.shelf_life_days = None

                # If shelf life changed, update all active FIFO entries
                if old_shelf_life != sku.shelf_life_days:
                    from ...blueprints.expiration.services import ExpirationService

                    # Get all active FIFO entries for this SKU
                    fifo_entries = ProductSKUHistory.query.filter(
                        ProductSKUHistory.sku_id == sku_id,
                        ProductSKUHistory.remaining_quantity > 0,
                        ProductSKUHistory.original_quantity.isnot(None)  # Only addition entries
                    ).all()

                    for entry in fifo_entries:
                        entry.is_perishable = True
                        entry.shelf_life_days = sku.shelf_life_days

                        # Calculate new expiration date based on batch completion or timestamp
                        if entry.batch_id:
                            # Use batch completion date if available
                            batch_expiration = ExpirationService.get_batch_expiration_date(entry.batch_id)
                            if batch_expiration:
                                entry.expiration_date = batch_expiration
                        elif entry.timestamp:
                            # Use entry timestamp as fallback
                            entry.expiration_date = ExpirationService.calculate_expiration_date(
                                entry.timestamp, sku.shelf_life_days
                            )

                    flash(f'Updated shelf life for {len(fifo_entries)} FIFO entries', 'info')
        else:
            sku.shelf_life_days = None

        db.session.commit()
        flash('SKU details updated successfully', 'success')

    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating SKU details: {str(e)}', 'error')

    return redirect(url_for('product_inventory.view_sku', sku_id=sku_id))