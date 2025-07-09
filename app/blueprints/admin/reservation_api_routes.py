
from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Reservation
from ...services.inventory_adjustment import process_inventory_adjustment
from ...services.reservation_service import ReservationService
from app.blueprints.fifo.services import FIFOService
import logging

logger = logging.getLogger(__name__)

reservation_api_bp = Blueprint('reservation_api', __name__, url_prefix='/api/reservations')

@reservation_api_bp.route('/create', methods=['POST'])
@login_required
def create_reservation():
    """Create a new reservation - deducts from available inventory"""
    # Check permission
    from ...utils.permissions import has_permission
    if not has_permission('inventory.reserve'):
        return jsonify({'error': 'Insufficient permissions to create reservations'}), 403
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['sku_code', 'quantity', 'order_id']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields: sku_code, quantity, order_id'}), 400
    
    # Find SKU by code
    sku = ProductSKU.query.filter_by(
        sku_code=data['sku_code'],
        organization_id=current_user.organization_id,
        is_active=True
    ).first()
    
    if not sku:
        return jsonify({'error': 'SKU not found or inactive'}), 404
    
    try:
        # Use centralized inventory adjustment for reservation
        success = process_inventory_adjustment(
            item_id=sku.inventory_item_id,
            quantity=float(data['quantity']),
            change_type='reserved',
            unit=sku.unit,
            notes=f"Reserved for order {data['order_id']}",
            created_by=current_user.id,
            item_type='product',
            customer=data.get('customer'),
            sale_price=float(data['sale_price']) if data.get('sale_price') else None,
            order_id=data['order_id']
        )
        
        if success:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Reserved {data["quantity"]} {sku.unit} for order {data["order_id"]}',
                'remaining_quantity': sku.quantity
            })
        else:
            return jsonify({'error': 'Failed to create reservation'}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating reservation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@reservation_api_bp.route('/release/<int:reservation_id>', methods=['POST'])
@login_required
def release_reservation(reservation_id):
    """Release a reservation - credits back to original FIFO lots"""
    try:
        success = FIFOService.release_reservation(reservation_id)
        
        if success:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Reservation released successfully'
            })
        else:
            return jsonify({'error': 'Failed to release reservation'}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error releasing reservation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@reservation_api_bp.route('/convert-to-sale/<int:reservation_id>', methods=['POST'])
@login_required
def convert_reservation_to_sale(reservation_id):
    """Convert a reservation to a sale"""
    reservation = Reservation.query.get(reservation_id)
    if not reservation or reservation.status != 'active':
        return jsonify({'error': 'Reservation not found or not active'}), 404
    
    try:
        # Mark reservation as converted
        reservation.mark_converted_to_sale()
        
        # Create sale history entry (reservation already deducted inventory)
        from app.models.product import ProductSKUHistory
        
        sale_entry = ProductSKUHistory(
            inventory_item_id=reservation.product_item_id,
            quantity_used=reservation.quantity,
            remaining_quantity=0,  # Already deducted
            change_type='sale',
            unit=reservation.unit,
            unit_cost=reservation.unit_cost,
            notes=f"Sale from reservation {reservation.order_id}",
            customer=reservation.customer if hasattr(reservation, 'customer') else None,
            sale_price=reservation.sale_price,
            order_id=reservation.order_id,
            created_by=current_user.id,
            organization_id=current_user.organization_id
        )
        db.session.add(sale_entry)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Reservation converted to sale successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error converting reservation to sale: {str(e)}")
        return jsonify({'error': str(e)}), 500

@reservation_api_bp.route('/expire-old', methods=['POST'])
@login_required
def expire_old_reservations():
    """Expire reservations that have passed their expiration date"""
    from datetime import datetime
    
    try:
        # Find expired reservations
        expired_reservations = Reservation.query.filter(
            Reservation.status == 'active',
            Reservation.expires_at.isnot(None),
            Reservation.expires_at < datetime.utcnow(),
            Reservation.organization_id == current_user.organization_id
        ).all()
        
        count = 0
        for reservation in expired_reservations:
            # Release the reservation (credits back to FIFO)
            success = FIFOService.release_reservation(reservation.id)
            if success:
                reservation.mark_expired()
                count += 1
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Expired {count} reservations',
            'expired_count': count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error expiring reservations: {str(e)}")
        return jsonify({'error': str(e)}), 500
