from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
from ...models.product import ProductSKUHistory
from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment
from app.blueprints.fifo.services import FIFOService
import logging

# Set up logger for product inventory operations
logger = logging.getLogger(__name__)

product_inventory_bp = Blueprint('product_inventory', __name__, url_prefix='/products/inventory')

@product_inventory_bp.route('/adjust/<int:inventory_item_id>', methods=['POST'])
@login_required
def adjust_sku_inventory(inventory_item_id):
    """SKU inventory adjustment - uses centralized inventory adjustment service"""
    logger.info(f"=== PRODUCT INVENTORY ADJUSTMENT START ===")
    logger.info(f"Inventory Item ID: {inventory_item_id}")
    logger.info(f"User: {current_user.id} ({current_user.username if hasattr(current_user, 'username') else 'unknown'})")
    logger.info(f"Organization: {current_user.organization_id}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request is JSON: {request.is_json}")

    # The sku_id parameter IS the inventory_item_id (primary key of ProductSKU)
    sku = ProductSKU.query.filter_by(
        inventory_item_id=inventory_item_id,
        organization_id=current_user.organization_id
    ).first()

    logger.info(f"SKU lookup result: {sku}")
    if sku:
        logger.info(f"SKU details - inventory_item_id: {sku.inventory_item_id}, Product: {sku.product.name if sku.product else 'No product'}, Variant: {sku.variant.name if sku.variant else 'No variant'}")
        logger.info(f"SKU inventory item: {sku.inventory_item}")
        if sku.inventory_item:
            logger.info(f"Current inventory quantity: {sku.inventory_item.quantity}")
    else:
        logger.error(f"SKU not found for inventory_item_id: {inventory_item_id}, org: {current_user.organization_id}")

    if not sku:
        logger.error(f"SKU not found for ID: {inventory_item_id}, org: {current_user.organization_id}")
        if request.is_json:
            return jsonify({'error': 'SKU not found'}), 404
        flash('SKU not found', 'error')
        return redirect(url_for('products.product_list'))

    # Parse request data
    if request.is_json:
        data = request.get_json()
        logger.info(f"JSON request data: {data}")
    else:
        data = request.form.to_dict()
        logger.info(f"Form request data: {data}")

    # Extract required fields
    quantity = data.get('quantity')
    change_type = data.get('change_type')

    logger.info(f"Extracted quantity: {quantity} (type: {type(quantity)})")
    logger.info(f"Extracted change_type: {change_type}")

    # Allow empty quantity for recount (will be treated as 0)
    if quantity is None or quantity == '':
        logger.info(f"Empty quantity detected. Change type: {change_type}")
        if change_type == 'recount':
            quantity = 0
            logger.info("Set quantity to 0 for recount operation")
        else:
            error_msg = 'Quantity is required'
            logger.error(f"Quantity validation failed: {error_msg}")
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('sku.view_sku', sku_id=inventory_item_id))

    if not change_type:
        error_msg = 'Change type is required'
        logger.error(f"Change type validation failed: {error_msg}")
        if request.is_json:
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('sku.view_sku', sku_id=inventory_item_id))

    try:
        # Convert and validate quantity - allow 0 for recount
        logger.info(f"Converting quantity '{quantity}' to float")
        quantity = float(quantity)
        logger.info(f"Converted quantity: {quantity}")

        # For deduction types, ensure quantity is positive here but will be made negative by centralized service
        if change_type in ['sale', 'spoil', 'trash', 'damaged', 'expired', 'gift', 'sample', 'tester']:
            if quantity < 0:
                logger.error(f"Quantity should be positive for deduction type: {change_type}")
                raise ValueError('Quantity should be positive for deduction operations')
        elif quantity < 0 and change_type not in ['recount']:
            logger.error(f"Negative quantity not allowed for change_type: {change_type}")
            raise ValueError('Quantity cannot be negative')

        # Extract optional fields
        notes = data.get('notes', '')
        unit = data.get('unit', sku.unit)
        customer = data.get('customer')
        sale_price = float(data.get('sale_price')) if data.get('sale_price') else None
        order_id = data.get('order_id')
        # Handle both 'cost_override' and 'restock_cost' field names
        cost_override = None
        if data.get('cost_override'):
            cost_override = float(data.get('cost_override'))
        elif data.get('restock_cost'):
            cost_override = float(data.get('restock_cost'))

        logger.info(f"Optional fields extracted:")
        logger.info(f"  - notes: {notes}")
        logger.info(f"  - unit: {unit}")
        logger.info(f"  - customer: {customer}")
        logger.info(f"  - sale_price: {sale_price}")
        logger.info(f"  - order_id: {order_id}")
        logger.info(f"  - cost_override: {cost_override}")

        # Validate order ID for reservations
        if change_type == 'reserved' and not order_id:
            error_msg = 'Order ID is required for reservations'
            logger.error(f"Order ID validation failed for reservation: {error_msg}")
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('sku.view_sku', sku_id=inventory_item_id))

        # Handle expiration data
        custom_expiration_date = None
        custom_shelf_life_days = None
        if data.get('shelf_life_days'):
            try:
                custom_shelf_life_days = int(data.get('shelf_life_days'))
                logger.info(f"Custom shelf life days: {custom_shelf_life_days}")
                if data.get('expiration_date'):
                    from datetime import datetime
                    custom_expiration_date = datetime.strptime(data.get('expiration_date'), '%Y-%m-%d').date()
                    logger.info(f"Custom expiration date: {custom_expiration_date}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing expiration data: {e}")

        # Handle unreserve specially - release all reservations for order ID
        if change_type == 'unreserved':
            if not order_id:
                error_msg = 'Order ID is required to release reservations'
                logger.error(f"Order ID validation failed for unreserve: {error_msg}")
                if request.is_json:
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('sku.view_sku', sku_id=inventory_item_id))

            logger.info(f"=== RELEASING ALL RESERVATIONS FOR ORDER: {order_id} ===")
            
            # Find all active reservations for this order
            from app.models.product import ProductSKUHistory
            reservations = ProductSKUHistory.query.filter(
                ProductSKUHistory.inventory_item_id == inventory_item_id,
                ProductSKUHistory.change_type == 'reserved_allocation',
                ProductSKUHistory.order_id == order_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == current_user.organization_id
            ).all()

            if not reservations:
                error_msg = f'No active reservations found for order ID: {order_id}'
                logger.error(error_msg)
                if request.is_json:
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('sku.view_sku', sku_id=inventory_item_id))

            # Calculate total quantity to release
            total_to_release = sum(res.remaining_quantity for res in reservations)
            logger.info(f"Releasing {total_to_release} units from {len(reservations)} reservation entries")

            # Use FIFO service to release the reservation
            try:
                from app.blueprints.fifo.services import FIFOService
                success = FIFOService.release_reservation(
                    inventory_item_id=inventory_item_id,
                    quantity=total_to_release,
                    order_id=order_id,
                    notes=notes or f"Released all reservations for order {order_id}",
                    created_by=current_user.id
                )

                if success:
                    db.session.commit()
                    flash(f'Released {total_to_release} units from order {order_id}', 'success')
                else:
                    flash('Error releasing reservations', 'error')
            except Exception as e:
                db.session.rollback()
                error_msg = f'Error releasing reservations: {str(e)}'
                logger.error(error_msg)
                if request.is_json:
                    return jsonify({'error': error_msg}), 500
                flash(error_msg, 'error')

            logger.info(f"=== PRODUCT INVENTORY ADJUSTMENT END ===")
            if not request.is_json:
                return redirect(url_for('sku.view_sku', inventory_item_id=inventory_item_id))
            return None

        # Handle recount separately with available + reserved split
        if change_type == 'recount':
            logger.info("=== DUAL RECOUNT: Available + Reserved ===")
            
            # Get separate counts for available and reserved
            available_qty = float(data.get('available_quantity', 0))
            reserved_qty = float(data.get('reserved_quantity', 0))
            
            logger.info(f"Recounting inventory item {inventory_item_id}: {available_qty} available, {reserved_qty} reserved")

            # Store original quantities
            original_available = sku.inventory_item.quantity or 0
            original_reserved = sku.reserved_quantity or 0

            # 1. Clear all existing reservation allocations
            from app.models.product import ProductSKUHistory
            existing_reservations = ProductSKUHistory.query.filter(
                ProductSKUHistory.inventory_item_id == inventory_item_id,
                ProductSKUHistory.change_type == 'reserved_allocation',
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == current_user.organization_id
            ).all()
            
            for reservation in existing_reservations:
                reservation.remaining_quantity = 0  # Clear existing reservations
                
            # 2. Set available quantity (this becomes the new item.quantity)
            sku.inventory_item.quantity = available_qty
            
            # 3. Create new reservation allocation if needed
            if reserved_qty > 0:
                FIFOService.add_fifo_entry(
                    inventory_item_id=inventory_item_id,
                    quantity=0,  # No change to total inventory
                    change_type='reserved_allocation',
                    unit=unit or sku.unit or 'count',
                    notes=f"Recount: Found {reserved_qty} reserved units",
                    created_by=current_user.id,
                    reserved_quantity=reserved_qty
                )
            
            # 4. Create recount summary entry
            total_change = (available_qty + reserved_qty) - (original_available + original_reserved)
            if total_change != 0:
                FIFOService.add_fifo_entry(
                    inventory_item_id=inventory_item_id,
                    quantity=total_change,
                    change_type='recount',
                    unit=unit or sku.unit or 'count',
                    notes=f"Recount: {original_available}+{original_reserved} → {available_qty}+{reserved_qty}",
                    created_by=current_user.id
                )

                # Calculate the actual change for summary entry
                qty_change = quantity - original_quantity

                # Only create summary entry if there was an actual change
                if qty_change != 0:
                    # Use the proper FIFO service instead of manual generation
                    if qty_change > 0:
                        # For positive changes, create a proper FIFO entry
                        FIFOService.add_fifo_entry(
                            inventory_item_id=inventory_item_id,
                            quantity=qty_change,
                            change_type='recount',
                            unit=unit or sku.unit or 'count',
                            notes=f"Product recount: {original_quantity} → {quantity}",
                            cost_per_unit=sku.inventory_item.cost_per_unit if sku.inventory_item else None,
                            created_by=current_user.id
                        )
                    else:
                        # For negative changes, create summary history using FIFO service
                        # This ensures consistent FIFO code generation
                        FIFOService.create_deduction_history(
                            inventory_item_id=inventory_item_id,
                            deduction_plan=[(0, abs(qty_change), sku.inventory_item.cost_per_unit if sku.inventory_item else None)],
                            change_type='recount',
                            notes=f"Product recount: {original_quantity} → {quantity}",
                            created_by=current_user.id
                        )

                db.session.commit()
                flash('Product inventory recounted successfully', 'success')
            else:
                flash('Error performing recount', 'error')
        else:
            # Use centralized adjustment service for non-recount operations
            try:
                logger.info("=== CALLING CENTRALIZED INVENTORY ADJUSTMENT ===")
                logger.info("Parameters:")
                logger.info(f"  - item_id (inventory_item_id): {inventory_item_id}")
                logger.info(f"  - quantity: {quantity}")
                logger.info(f"  - change_type: {change_type}")
                logger.info(f"  - unit: {unit}")
                logger.info(f"  - notes: {notes}")
                logger.info(f"  - created_by: {current_user.id}")
                logger.info(f"  - item_type: product")
                logger.info(f"  - customer: {customer}")
                logger.info(f"  - sale_price: {sale_price}")
                logger.info(f"  - order_id: {order_id}")
                logger.info(f"  - cost_override: {cost_override}")
                logger.info(f"  - custom_expiration_date: {custom_expiration_date}")
                logger.info(f"  - custom_shelf_life_days: {custom_shelf_life_days}")

                success = process_inventory_adjustment(
                    item_id=inventory_item_id,
                    quantity=quantity,
                    change_type=change_type,
                    unit=unit,
                    notes=notes,
                    created_by=current_user.id,
                    item_type='product',
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    cost_override=cost_override,
                    custom_expiration_date=custom_expiration_date,
                    custom_shelf_life_days=custom_shelf_life_days
                )

                if success:
                    flash('Product inventory adjusted successfully', 'success')
                else:
                    flash('Error adjusting product inventory', 'error')

            except ValueError as e:
                logger.error(f"ValueError in SKU inventory adjustment: {str(e)}")
                flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        error_msg = f'Error adjusting inventory: {str(e)}'
        logger.error(f"Exception in SKU inventory adjustment: {error_msg}")
        logger.exception("Full traceback:")
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, 'error')

    # Redirect for form submissions
    logger.info(f"=== PRODUCT INVENTORY ADJUSTMENT END ===")
    if not request.is_json:
        logger.info(f"Redirecting to SKU view: {inventory_item_id}")
        return redirect(url_for('sku.view_sku', inventory_item_id=inventory_item_id))
    return None

@product_inventory_bp.route('/fifo-status/<int:sku_id>')
@login_required
def get_sku_fifo_status(sku_id):
    """Get FIFO status for SKU using unified inventory system"""
    logger.info(f"=== FIFO STATUS REQUEST ===")
    logger.info(f"SKU ID: {sku_id}")

    sku = ProductSKU.query.filter_by(
        inventory_item_id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        logger.error(f"SKU not found for FIFO status: {sku_id}")
        return jsonify({'error': 'SKU not found'}), 404

    logger.info(f"Found SKU: {sku.inventory_item_id}, Product: {sku.product.name if sku.product else 'Unknown'}")

    from ...models import InventoryHistory
    from datetime import datetime

    today = datetime.now().date()
    inventory_item_id = sku.inventory_item_id

    # Get fresh FIFO entries (not expired, with remaining quantity)
    fresh_entries = InventoryHistory.query.filter(
        InventoryHistory.inventory_item_id == inventory_item_id,
        InventoryHistory.remaining_quantity > 0,
        InventoryHistory.organization_id == current_user.organization_id,
        db.or_(
            InventoryHistory.expiration_date.is_(None),  # Non-perishable
            InventoryHistory.expiration_date >= today    # Not expired yet
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

    # Get expired FIFO entries (frozen, with remaining quantity)
    expired_entries = InventoryHistory.query.filter(
        InventoryHistory.inventory_item_id == inventory_item_id,
        InventoryHistory.remaining_quantity > 0,
        InventoryHistory.organization_id == current_user.organization_id,
        InventoryHistory.expiration_date.isnot(None),
        InventoryHistory.expiration_date < today
    ).order_by(InventoryHistory.timestamp.asc()).all()

    fresh_total = sum(entry.remaining_quantity for entry in fresh_entries)
    expired_total = sum(entry.remaining_quantity for entry in expired_entries)

    return jsonify({
        'sku_id': sku_id,
        'inventory_item_id': inventory_item_id,
        'total_quantity': sku.quantity,
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
    """Dispose of expired SKU inventory using unified inventory system"""
    sku = ProductSKU.query.filter_by(
        inventory_item_id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found'}), 404

    data = request.get_json() if request.is_json else request.form
    disposal_type = data.get('disposal_type', 'expired_disposal')
    notes = data.get('notes', 'Expired inventory disposal')

    from ...models import InventoryHistory
    from datetime import datetime

    today = datetime.now().date()
    inventory_item_id = sku.inventory_item_id

    # Get all expired entries with remaining quantity
    expired_entries = InventoryHistory.query.filter(
        InventoryHistory.inventory_item_id == inventory_item_id,
        InventoryHistory.remaining_quantity > 0,
        InventoryHistory.organization_id == current_user.organization_id,
        InventoryHistory.expiration_date.isnot(None),
        InventoryHistory.expiration_date < today
    ).all()

    if not expired_entries:
        return jsonify({'error': 'No expired inventory found'}), 400

    total_expired = sum(entry.remaining_quantity for entry in expired_entries)

    try:
        # Use centralized service to dispose of expired inventory
        success = process_inventory_adjustment(
            item_id=inventory_item_id,
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

    # Find SKU by code with organization scoping
    sku = ProductSKU.query.filter_by(
        sku_code=data['sku_code'],
        organization_id=current_user.organization_id,
        is_active=True
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found or inactive'}), 404

    try:
        # Use centralized inventory adjustment which properly calls FIFO service
        success = process_inventory_adjustment(
            item_id=sku.inventory_item_id,
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
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Sale processed successfully',
                'remaining_quantity': sku.quantity
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

    # Find SKU by code with organization scoping
    sku = ProductSKU.query.filter_by(
        sku_code=data['sku_code'],
        organization_id=current_user.organization_id,
        is_active=True
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found or inactive'}), 404

    try:
        # Use centralized inventory adjustment which properly calls FIFO service
        success = process_inventory_adjustment(
            item_id=sku.inventory_item_id,
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
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Return processed successfully',
                'new_quantity': sku.quantity
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
    logger.info(f"=== RESERVE INVENTORY REQUEST ===")
    logger.info(f"SKU ID: {sku_id}")

    sku = ProductSKU.query.filter_by(
        inventory_item_id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        logger.error(f"SKU not found for reservation: {sku_id}")
        return jsonify({'error': 'SKU not found'}), 404

    logger.info(f"Found SKU for reservation: {sku.inventory_item_id}")

    data = request.get_json() if request.is_json else request.form
    quantity = data.get('quantity')
    notes = data.get('notes', 'Inventory reservation')

    if not quantity:
        return jsonify({'error': 'Quantity is required'}), 400

    try:
        # Use centralized inventory adjustment which properly calls FIFO service
        success = process_inventory_adjustment(
            item_id=sku.inventory_item_id,
            quantity=float(quantity),
            change_type='reserved',
            unit=sku.unit,
            notes=notes,
            created_by=current_user.id,
            item_type='product',
            order_id=data.get('order_id')
        )

        if success:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Inventory reserved successfully',
                'available_quantity': sku.quantity,
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

        # Create a mock product/variant for the service to use
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

            # Use centralized inventory adjustment which properly calls FIFO service
            success = process_inventory_adjustment(
                item_id=bulk_sku.inventory_item_id,
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

@product_inventory_bp.route('/inventory/add-from-batch', methods=['POST'])
@login_required
def add_inventory_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_id = data.get('product_id')
    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    size_label = data.get('size_label')
    quantity = data.get('quantity')

    if not batch_id or (not product_id and not product_name):
        return jsonify({'error': 'Batch ID and Product ID or Name are required'}), 400

    try:
        # Get product name from ID if provided - with org scoping
        if product_id:
            base_sku = ProductSKU.query.filter_by(
                id=product_id,
                organization_id=current_user.organization_id
            ).first()
            if not base_sku:
                return jsonify({'error': 'Product not found'}), 404
            product_name = base_sku.product_name

        # Get or create the SKU
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            size_label=size_label or 'Bulk'
        )

        # Use the centralized inventory adjustment service which properly calls FIFO service
        success = process_inventory_adjustment(
            item_id=sku.inventory_item_id,
            quantity=quantity,
            change_type='finished_batch',  # Use standard change_type for batch completion
            unit=sku.unit,
            notes=f'Added from batch {batch_id}',
            batch_id=batch_id,
            created_by=current_user.id,
            item_type='product'
        )

        if success:
            db.session.commit()
            return jsonify({
                'success': True,
                'sku_id': sku.id,
                'message': f'Added {quantity} {sku.unit} to {sku.display_name}'
            })
        else:
            return jsonify({'error': 'Failed to add inventory'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500