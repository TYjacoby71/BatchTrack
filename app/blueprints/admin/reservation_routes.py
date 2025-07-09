from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import and_, func, desc
from datetime import datetime, timedelta

from ...models import db, Reservation, InventoryItem
from ...services.pos_integration import POSIntegrationService
from ...utils.permissions import has_permission

reservation_bp = Blueprint('reservations', __name__)

@reservation_bp.route('/')
@login_required
def list_reservations():
    """List all reservations with filtering options"""
    status_filter = request.args.get('status', 'active')
    order_id_filter = request.args.get('order_id', '')

    query = Reservation.query

    # Apply filters
    if status_filter != 'all':
        query = query.filter(Reservation.status == status_filter)

    if order_id_filter:
        query = query.filter(Reservation.order_id.contains(order_id_filter))

    # Organization scoping
    if current_user.organization_id:
        query = query.filter(Reservation.organization_id == current_user.organization_id)

    reservations = query.order_by(desc(Reservation.created_at)).limit(100).all()

    # Get summary stats
    stats = {
        'total_active': Reservation.query.filter(
            and_(
                Reservation.status == 'active',
                Reservation.organization_id == current_user.organization_id
            )
        ).count(),
        'total_expired': Reservation.query.filter(
            and_(
                Reservation.status == 'expired',
                Reservation.organization_id == current_user.organization_id
            )
        ).count(),
        'total_converted': Reservation.query.filter(
            and_(
                Reservation.status == 'converted_to_sale',
                Reservation.organization_id == current_user.organization_id
            )
        ).count()
    }

    return render_template('admin/reservations.html', 
                         reservations=reservations, 
                         stats=stats,
                         status_filter=status_filter,
                         order_id_filter=order_id_filter)

@reservation_bp.route('/api/reservations/create', methods=['POST'])
@login_required
def create_reservation():
    """Create a new reservation via API"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['item_id', 'quantity', 'order_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create the reservation
        success, message = POSIntegrationService.reserve_inventory(
            item_id=data['item_id'],
            quantity=float(data['quantity']),
            order_id=data['order_id'],
            source=data.get('source', 'manual'),
            notes=data.get('notes', ''),
            sale_price=data.get('sale_price'),
            expires_in_hours=data.get('expires_in_hours')
        )

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/api/reservations/<order_id>/release', methods=['POST'])
@login_required
def release_reservation(order_id):
    """Release a reservation by order ID"""
    try:
        success, message = POSIntegrationService.release_reservation(order_id)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/api/reservations/<order_id>/confirm_sale', methods=['POST'])
@login_required
def confirm_sale(order_id):
    """Convert reservation to sale"""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')

        success, message = POSIntegrationService.confirm_sale(order_id, notes)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/api/reservations/<order_id>/details')
@login_required
def get_reservation_details(order_id):
    """Get detailed information about a reservation"""
    try:
        from ...services.reservation_service import ReservationService
        details = ReservationService.get_reservation_details_for_order(order_id)
        return jsonify({'reservations': details})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/api/reservations/cleanup_expired', methods=['POST'])
@login_required
def cleanup_expired():
    """Clean up expired reservations"""
    try:
        count = POSIntegrationService.cleanup_expired_reservations()
        return jsonify({'success': True, 'message': f'Cleaned up {count} expired reservations'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/api/inventory/<int:item_id>/reservations')
@login_required
def get_item_reservations(item_id):
    """Get all reservations for a specific inventory item"""
    try:
        reservations = Reservation.query.filter(
            and_(
                Reservation.product_item_id == item_id,
                Reservation.organization_id == current_user.organization_id
            )
        ).order_by(desc(Reservation.created_at)).all()

        result = []
        for reservation in reservations:
            result.append({
                'id': reservation.id,
                'order_id': reservation.order_id,
                'quantity': reservation.quantity,
                'unit': reservation.unit,
                'status': reservation.status,
                'source': reservation.source,
                'created_at': reservation.created_at.isoformat() if reservation.created_at else None,
                'expires_at': reservation.expires_at.isoformat() if reservation.expires_at else None,
                'sale_price': reservation.sale_price,
                'notes': reservation.notes
            })

        return jsonify({'reservations': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500