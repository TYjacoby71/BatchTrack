
from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment

product_inventory_bp = Blueprint('product_inventory', __name__, url_prefix='/products/inventory')

@product_inventory_bp.route('/adjust/<int:sku_id>', methods=['POST'])
@login_required
def adjust_sku_inventory(sku_id):
    """Comprehensive SKU inventory adjustment endpoint with FIFO and expired inventory handling"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        if request.is_json:
            return jsonify({'error': 'SKU not found'}), 404
        flash('SKU not found', 'error')
        return redirect(url_for('products.product_list'))
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
        quantity = data.get('quantity')
        change_type = data.get('change_type')
        notes = data.get('notes')
        unit = data.get('unit', sku.unit)
        customer = data.get('customer')
        sale_price = data.get('sale_price')
        order_id = data.get('order_id')
        cost_override = data.get('cost_override')
        target_expired = data.get('target_expired', False)  # Allow targeting expired inventory
        is_perishable = data.get('is_perishable', False)
        shelf_life_days = data.get('shelf_life_days')
        expiration_date = data.get('expiration_date')
    else:
        quantity = request.form.get('quantity')
        change_type = request.form.get('change_type')
        notes = request.form.get('notes')
        unit = request.form.get('unit', sku.unit)
        customer = request.form.get('customer')
        sale_price = request.form.get('sale_price')
        order_id = request.form.get('order_id')
        cost_override = request.form.get('cost_override')
        target_expired = request.form.get('target_expired', 'false').lower() == 'true'
        is_perishable = request.form.get('is_perishable') == 'on'
        shelf_life_days = request.form.get('shelf_life_days')
        expiration_date = request.form.get('expiration_date')

    # Validate required fields
    if not quantity or not change_type:


@product_inventory_bp.route('/fifo-status/<int:sku_id>')
@login_required
def get_sku_fifo_status(sku_id):
    """Get FIFO status for SKU including expired entries (like raw inventory system)"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found'}), 404
    
    from ...models import ProductSKUHistory
    from datetime import datetime
    
    today = datetime.now().date()
    
    # Get fresh FIFO entries (not expired, with remaining quantity)
    fresh_entries = ProductSKUHistory.query.filter(
        ProductSKUHistory.sku_id == sku_id,
        ProductSKUHistory.remaining_quantity > 0,
        db.or_(
            ProductSKUHistory.expiration_date.is_(None),  # Non-perishable
            ProductSKUHistory.expiration_date >= today    # Not expired yet
        )
    ).order_by(ProductSKUHistory.timestamp.asc()).all()
    
    # Get expired FIFO entries (frozen, with remaining quantity)
    expired_entries = ProductSKUHistory.query.filter(
        ProductSKUHistory.sku_id == sku_id,
        ProductSKUHistory.remaining_quantity > 0,
        ProductSKUHistory.expiration_date.isnot(None),
        ProductSKUHistory.expiration_date < today
    ).order_by(ProductSKUHistory.timestamp.asc()).all()
    
    fresh_total = sum(entry.remaining_quantity for entry in fresh_entries)
    expired_total = sum(entry.remaining_quantity for entry in expired_entries)
    
    return jsonify({
        'sku_id': sku_id,
        'total_quantity': sku.current_quantity,
        'fresh_quantity': fresh_total,
        'expired_quantity': expired_total,
        'fresh_entries_count': len(fresh_entries),
        'expired_entries_count': len(expired_entries),
        'fresh_entries': [{
            'id': entry.id,
            'remaining_quantity': entry.remaining_quantity,
            'expiration_date': entry.expiration_date.isoformat() if entry.expiration_date else None,
            'timestamp': entry.timestamp.isoformat(),
            'change_type': entry.change_type
        } for entry in fresh_entries],
        'expired_entries': [{
            'id': entry.id,
            'remaining_quantity': entry.remaining_quantity,
            'expiration_date': entry.expiration_date.isoformat(),
            'timestamp': entry.timestamp.isoformat(),
            'change_type': entry.change_type
        } for entry in expired_entries]
    })

@product_inventory_bp.route('/dispose-expired/<int:sku_id>', methods=['POST'])
@login_required
def dispose_expired_sku(sku_id):
    """Dispose of expired SKU inventory (like raw inventory system)"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found'}), 404
    
    data = request.get_json() if request.is_json else request.form
    disposal_type = data.get('disposal_type', 'expired_disposal')  # spoil, trash, expired_disposal
    notes = data.get('notes', 'Expired inventory disposal')
    
    from ...models import ProductSKUHistory
    from datetime import datetime
    
    today = datetime.now().date()
    
    # Get all expired entries with remaining quantity
    expired_entries = ProductSKUHistory.query.filter(
        ProductSKUHistory.sku_id == sku_id,
        ProductSKUHistory.remaining_quantity > 0,
        ProductSKUHistory.expiration_date.isnot(None),
        ProductSKUHistory.expiration_date < today
    ).all()
    
    if not expired_entries:
        return jsonify({'error': 'No expired inventory found'}), 400
    
    total_expired = sum(entry.remaining_quantity for entry in expired_entries)
    
    try:
        # Use centralized service to dispose of expired inventory
        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=total_expired,
            change_type=disposal_type,
            unit=sku.unit,
            notes=f"{notes} - {len(expired_entries)} expired lots",
            created_by=current_user.id,
            item_type='product'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Disposed {total_expired} {sku.unit} of expired inventory',
                'disposed_quantity': total_expired,
                'disposed_lots': len(expired_entries)
            })
        else:
            return jsonify({'error': 'Failed to dispose expired inventory'}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


        error_msg = 'Quantity and change type are required'
        if request.is_json:
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('products.view_sku', sku_id=sku_id))

    try:
        # Convert numeric values
        quantity = float(quantity)
        sale_price_float = float(sale_price) if sale_price else None
        cost_override_float = float(cost_override) if cost_override else None
        
        # Handle perishable inventory
        custom_expiration_date = None
        custom_shelf_life_days = None
        
        if is_perishable and shelf_life_days:
            try:
                custom_shelf_life_days = int(shelf_life_days)
                # Parse expiration date if provided
                if expiration_date:
                    from datetime import datetime
                    custom_expiration_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass

        # For disposal operations, auto-target expired inventory if available
        if change_type in ['spoil', 'trash', 'expired_disposal'] and not target_expired:
            from ...models import ProductSKUHistory
            from datetime import datetime
            
            # Check for expired SKU history entries
            today = datetime.now().date()
            expired_entries = ProductSKUHistory.query.filter(
                ProductSKUHistory.sku_id == sku_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.expiration_date.isnot(None),
                ProductSKUHistory.expiration_date < today
            ).all()
            
            expired_total = sum(entry.remaining_quantity for entry in expired_entries)
            if expired_total >= quantity:
                target_expired = True

        # Use centralized inventory adjustment service
        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=quantity,
            change_type=change_type,
            unit=unit,
            notes=notes,
            created_by=current_user.id,
            item_type='product',
            customer=customer,
            sale_price=sale_price_float,
            order_id=order_id,
            cost_override=cost_override_float,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if success:
            message = f'SKU inventory adjusted successfully'
            if target_expired and change_type in ['spoil', 'trash', 'expired_disposal']:
                message += ' (expired inventory processed first)'
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': message,
                    'new_quantity': sku.current_quantity,
                    'processed_expired': target_expired
                })
            flash(message, 'success')
        else:
            error_msg = 'Error adjusting inventory'
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(error_msg, 'error')

    except ValueError as e:
        error_msg = str(e)
        if request.is_json:
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
    except Exception as e:
        db.session.rollback()
        error_msg = f'Error adjusting inventory: {str(e)}'
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, 'error')

    # Redirect for form submissions
    if not request.is_json:
        return redirect(url_for('products.view_sku', sku_id=sku_id))

@product_inventory_bp.route('/webhook/sale', methods=['POST'])
@login_required
def process_sale_webhook():
    """Process sales from external systems (Shopify, Etsy, etc.)"""
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400
    
    data = request.get_json()
    
    # Validate webhook data
    required_fields = ['sku_code', 'quantity', 'sale_price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Find SKU by code
    sku = ProductSKU.query.filter_by(
        sku_code=data['sku_code'],
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found'}), 404
    
    try:
        success = process_inventory_adjustment(
            item_id=sku.id,
            quantity=float(data['quantity']),
            change_type='sold',
            unit=sku.unit,
            notes=f"Sale from {data.get('source', 'external system')}",
            created_by=current_user.id,
            item_type='product',
            customer=data.get('customer'),
            sale_price=float(data['sale_price']),
            order_id=data.get('order_id')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Sale processed successfully',
                'remaining_quantity': sku.current_quantity
            })
        else:
            return jsonify({'error': 'Failed to process sale'}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product_inventory_bp.route('/webhook/return', methods=['POST'])
@login_required
def process_return_webhook():
    """Process returns from external systems"""
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400
    
    data = request.get_json()
    
    # Validate webhook data
    required_fields = ['sku_code', 'quantity']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Find SKU by code
    sku = ProductSKU.query.filter_by(
        sku_code=data['sku_code'],
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found'}), 404
    
    try:
        success = process_inventory_adjustment(
            item_id=sku.id,
            quantity=float(data['quantity']),
            change_type='returned',
            unit=sku.unit,
            notes=f"Return from {data.get('source', 'external system')}",
            created_by=current_user.id,
            item_type='product',
            customer=data.get('customer'),
            order_id=data.get('original_order_id')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Return processed successfully',
                'new_quantity': sku.current_quantity
            })
        else:
            return jsonify({'error': 'Failed to process return'}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product_inventory_bp.route('/reserve/<int:sku_id>', methods=['POST'])
@login_required
def reserve_inventory(sku_id):
    """Reserve inventory for pending orders"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found'}), 404
    
    data = request.get_json() if request.is_json else request.form
    quantity = data.get('quantity')
    notes = data.get('notes', 'Inventory reservation')


# Legacy compatibility routes - redirect to consolidated inventory adjustment
@product_inventory_bp.route('/legacy/adjust/<int:sku_id>', methods=['POST'])
@login_required 
def legacy_adjust_sku(sku_id):
    """Legacy route compatibility - redirects to main adjustment endpoint"""
    return adjust_sku_inventory(sku_id)

@product_inventory_bp.route('/api/adjust/<int:sku_id>', methods=['POST'])
@login_required
def api_adjust_sku_inventory(sku_id):
    """API endpoint for SKU inventory adjustments - same as main adjustment but ensures JSON response"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found'}), 404

    data = request.get_json() if request.is_json else request.form

    quantity = data.get('quantity')
    change_type = data.get('change_type')
    notes = data.get('notes')

    if not quantity or not change_type:
        return jsonify({'error': 'Quantity and change type are required'}), 400

    try:
        # Get additional product-specific parameters
        customer = data.get('customer')
        sale_price = data.get('sale_price')
        order_id = data.get('order_id')

        # Convert sale_price to float if provided
        sale_price_float = None
        if sale_price:
            try:
                sale_price_float = float(sale_price)
            except (ValueError, TypeError):
                pass

        # Use centralized inventory adjustment service
        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=float(quantity),
            change_type=change_type,
            unit=sku.unit,
            notes=notes,
            created_by=current_user.id,
            item_type='product',
            customer=customer,
            sale_price=sale_price_float,
            order_id=order_id
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'SKU inventory adjusted successfully',
                'new_quantity': sku.current_quantity
            })
        else:
            return jsonify({'error': 'Error adjusting inventory'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


    
    if not quantity:
        return jsonify({'error': 'Quantity is required'}), 400
    
    try:
        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=float(quantity),
            change_type='reserved',
            unit=sku.unit,
            notes=notes,
            created_by=current_user.id,
            item_type='product',
            order_id=data.get('order_id')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Inventory reserved successfully',
                'available_quantity': sku.current_quantity,
                'reserved_quantity': getattr(sku, 'reserved_quantity', 0)
            })
        else:
            return jsonify({'error': 'Failed to reserve inventory'}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product_inventory_bp.route('/add-from-batch', methods=['POST'])
@login_required
def add_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()
    
    batch_id = data.get('batch_id')
    product_id = data.get('product_id')
    variant_label = data.get('variant_label')
    quantity = data.get('quantity')
    container_overrides = data.get('container_overrides', {})
    
    if not batch_id or not product_id:
        return jsonify({'error': 'Batch ID and Product ID are required'}), 400
    
    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
            
        target_sku = ProductSKU.query.get(product_id)
        if not target_sku:
            return jsonify({'error': 'Target SKU not found'}), 404
        
        inventory_entries = []
        total_containerized = 0
        
        # Use BatchService to handle container processing and avoid duplication
        from ...services.batch_service import BatchService
        
        # Create a mock batch object for the service to use
        class MockBatch:
            def __init__(self, batch):
                self.id = batch.id
                self.label_code = batch.label_code
                self.containers = batch.containers
                self.extra_containers = batch.extra_containers
                self.expiration_date = batch.expiration_date
                self.shelf_life_days = batch.shelf_life_days
                self.output_unit = batch.output_unit
        
        mock_batch = MockBatch(batch)
        
        # Create a mock product/variant for the service
        class MockProduct:
            def __init__(self, name):
                self.name = name
        
        class MockVariant:
            def __init__(self, name):
                self.name = name
        
        mock_product = MockProduct(target_sku.product_name)
        mock_variant = MockVariant(variant_label)
        
        # Process containers using BatchService
        total_containerized += BatchService._process_batch_containers(
            batch.containers, container_overrides, mock_batch, mock_product, mock_variant, inventory_entries
        )
        
        total_containerized += BatchService._process_batch_containers(
            batch.extra_containers, container_overrides, mock_batch, mock_product, mock_variant, inventory_entries, is_extra=True
        )
        
        # Handle remaining bulk quantity
        bulk_quantity = quantity - total_containerized
        if bulk_quantity > 0:
            # Add to bulk SKU
            bulk_sku = target_sku
            if target_sku.size_label != 'Bulk':
                # Get or create bulk SKU for this product/variant
                bulk_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label='Bulk',
                    unit=batch.output_unit or target_sku.unit
                )
            
            success = process_inventory_adjustment(
                item_id=bulk_sku.id,
                quantity=bulk_quantity,
                change_type='finished_batch',
                unit=batch.output_unit or target_sku.unit,
                notes=f"From batch {batch.label_code} - Bulk remainder",
                batch_id=batch_id,
                created_by=current_user.id,
                item_type='product',
                custom_expiration_date=batch.expiration_date,
                custom_shelf_life_days=batch.shelf_life_days
            )
            
            if success:
                inventory_entries.append({
                    'sku_id': bulk_sku.id,
                    'quantity': bulk_quantity,
                    'type': 'bulk'
                })
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'inventory_entries': inventory_entries,
            'message': f'Successfully added product inventory from batch {batch.label_code}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
