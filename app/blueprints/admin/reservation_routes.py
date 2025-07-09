
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from ...models import db, InventoryItem
from ...models.product import ProductSKUHistory
from ...services.pos_integration import POSIntegrationService
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)

reservation_admin_bp = Blueprint('reservation_admin', __name__, url_prefix='/admin/reservations')

@reservation_admin_bp.route('/')
@login_required
def reservation_list():
    """Admin view of all active reservations"""
    # Get all active reservations grouped by SKU
    active_reservations = db.session.query(
        ProductSKUHistory.inventory_item_id,
        InventoryItem.name,
        ProductSKUHistory.order_id,
        ProductSKUHistory.remaining_quantity,
        ProductSKUHistory.unit,
        ProductSKUHistory.fifo_reference_id,
        ProductSKUHistory.timestamp,
        ProductSKUHistory.created_by
    ).join(InventoryItem).filter(
        and_(
            ProductSKUHistory.change_type == 'reserved_allocation',
            ProductSKUHistory.remaining_quantity > 0,
            ProductSKUHistory.organization_id == current_user.organization_id,
            InventoryItem.type == 'product-reserved'
        )
    ).order_by(ProductSKUHistory.timestamp.desc()).all()

    # Group by SKU
    reservation_groups = {}
    for res in active_reservations:
        sku_name = res.name.replace(' (Reserved)', '')
        if sku_name not in reservation_groups:
            reservation_groups[sku_name] = []
        
        reservation_groups[sku_name].append({
            'order_id': res.order_id,
            'quantity': res.remaining_quantity,
            'unit': res.unit,
            'batch_id': res.fifo_reference_id,
            'created_at': res.timestamp,
            'created_by': res.created_by
        })

    return render_template('admin/reservations.html', 
                         reservation_groups=reservation_groups)

@reservation_admin_bp.route('/api/by-sku/<int:sku_id>')
@login_required
def get_sku_reservations(sku_id):
    """Get reservations for a specific SKU"""
    # Find the reserved item for this SKU
    original_item = InventoryItem.query.get(sku_id)
    if not original_item:
        return jsonify({'error': 'SKU not found'}), 404

    reserved_item_name = f"{original_item.name} (Reserved)"
    reserved_item = InventoryItem.query.filter_by(
        name=reserved_item_name,
        type='product-reserved',
        organization_id=current_user.organization_id
    ).first()

    if not reserved_item:
        return jsonify({'reservations': []})

    # Get active reservations
    reservations = ProductSKUHistory.query.filter(
        and_(
            ProductSKUHistory.inventory_item_id == reserved_item.id,
            ProductSKUHistory.change_type == 'reserved_allocation',
            ProductSKUHistory.remaining_quantity > 0
        )
    ).order_by(ProductSKUHistory.timestamp.desc()).all()

    result = []
    for res in reservations:
        result.append({
            'order_id': res.order_id,
            'quantity': res.remaining_quantity,
            'unit': res.unit,
            'batch_id': res.fifo_reference_id,
            'created_at': res.timestamp.isoformat(),
            'notes': res.notes
        })

    return jsonify({'reservations': result})

@reservation_admin_bp.route('/api/release/<order_id>', methods=['POST'])
@login_required
def release_reservation_admin(order_id):
    """Admin endpoint to release a reservation"""
    success, message = POSIntegrationService.release_reservation(order_id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400

@reservation_admin_bp.route('/api/confirm-sale/<order_id>', methods=['POST'])
@login_required
def confirm_sale_admin(order_id):
    """Admin endpoint to convert reservation to sale"""
    data = request.get_json() or {}
    notes = data.get('notes', 'Manual sale confirmation')
    
    success, message = POSIntegrationService.confirm_sale(order_id, notes)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400

@reservation_admin_bp.route('/webhook/shopify/reserve', methods=['POST'])
def shopify_reserve_webhook():
    """Shopify webhook for creating reservations"""
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    
    # Validate webhook data
    required_fields = ['sku_id', 'quantity', 'order_id']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        success, message = POSIntegrationService.reserve_inventory(
            item_id=int(data['sku_id']),
            quantity=float(data['quantity']),
            order_id=data['order_id'],
            source='shopify',
            notes=data.get('notes')
        )

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.error(f"Error in Shopify reserve webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

@reservation_admin_bp.route('/webhook/shopify/cancel', methods=['POST'])
def shopify_cancel_webhook():
    """Shopify webhook for canceling reservations"""
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'order_id required'}), 400

    try:
        success, message = POSIntegrationService.release_reservation(order_id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.error(f"Error in Shopify cancel webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

@reservation_admin_bp.route('/webhook/shopify/fulfill', methods=['POST'])
def shopify_fulfill_webhook():
    """Shopify webhook for fulfilling orders (convert reservation to sale)"""
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'order_id required'}), 400

    try:
        success, message = POSIntegrationService.confirm_sale(
            order_id, 
            notes=f"Shopify fulfillment: {data.get('notes', '')}"
        )
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.error(f"Error in Shopify fulfill webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500
