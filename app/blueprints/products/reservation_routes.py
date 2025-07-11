from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import and_, func, desc
from datetime import datetime, timedelta

from ...models import db, Reservation, InventoryItem
from ...services.pos_integration import POSIntegrationService
from ...utils.permissions import has_permission

reservation_bp = Blueprint('reservations', __name__, url_prefix='/reservations')

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

    # Group reservations by SKU name for display
    reservation_groups = {}
    for reservation in reservations:
        if reservation.product_item:
            sku_name = reservation.product_item.name
            if sku_name not in reservation_groups:
                reservation_groups[sku_name] = []

            # Add reservation with additional data for display
            batch_label = None
            lot_number = None

            if reservation.source_batch_id and reservation.source_batch:
                batch_label = reservation.source_batch.label_code

            # Get lot information from FIFO entry if available
            if reservation.source_fifo_id:
                from ...models import InventoryHistory
                from ...models.product import ProductSKUHistory

                # Try to get lot information from either InventoryHistory or ProductSKUHistory
                fifo_entry = None
                if reservation.product_item and reservation.product_item.type == 'product':
                    fifo_entry = ProductSKUHistory.query.get(reservation.source_fifo_id)
                else:
                    fifo_entry = InventoryHistory.query.get(reservation.source_fifo_id)

                if fifo_entry and hasattr(fifo_entry, 'lot_number') and fifo_entry.lot_number:
                    lot_number = fifo_entry.lot_number

            reservation_data = {
                'order_id': reservation.order_id,
                'quantity': reservation.quantity,
                'unit': reservation.unit,
                'batch_id': reservation.source_batch_id,
                'batch_label': batch_label,
                'lot_number': lot_number,
                'source_batch_id': reservation.source_batch_id,  # Keep both for compatibility
                'created_at': reservation.created_at,
                'expires_at': reservation.expires_at,
                'sale_price': reservation.sale_price,
                'source': reservation.source,
                'notes': reservation.notes,
                'status': reservation.status
            }
            reservation_groups[sku_name].append(reservation_data)

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
                         reservation_groups=reservation_groups, 
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
        print(f"DEBUG: Attempting to release reservation for order_id: {order_id}")
        
        # First check if reservations exist for this order
        from ...models import Reservation
        reservations = Reservation.query.filter_by(order_id=order_id, status='active').all()
        print(f"DEBUG: Found {len(reservations)} active reservations for order {order_id}")
        
        for i, reservation in enumerate(reservations):
            print(f"DEBUG: Reservation {i+1}:")
            print(f"  - ID: {reservation.id}")
            print(f"  - Product Item ID: {reservation.product_item_id}")
            print(f"  - Quantity: {reservation.quantity}")
            print(f"  - Source FIFO ID: {reservation.source_fifo_id}")
            print(f"  - Source Batch ID: {reservation.source_batch_id}")
            print(f"  - Product Item: {reservation.product_item.name if reservation.product_item else 'None'}")
            
            # Check if source FIFO entry exists
            if reservation.source_fifo_id:
                from ...models import InventoryHistory
                from ...models.product import ProductSKUHistory
                
                if reservation.product_item and reservation.product_item.type == 'product':
                    fifo_entry = ProductSKUHistory.query.get(reservation.source_fifo_id)
                    print(f"  - FIFO Entry (ProductSKUHistory): {fifo_entry}")
                    if fifo_entry:
                        print(f"    - Lot Number: {fifo_entry.lot_number if hasattr(fifo_entry, 'lot_number') else 'N/A'}")
                        print(f"    - Remaining Quantity: {fifo_entry.remaining_quantity}")
                else:
                    fifo_entry = InventoryHistory.query.get(reservation.source_fifo_id)
                    print(f"  - FIFO Entry (InventoryHistory): {fifo_entry}")
                    if fifo_entry:
                        print(f"    - Lot Number: {fifo_entry.lot_number if hasattr(fifo_entry, 'lot_number') else 'N/A'}")
                        print(f"    - Remaining Quantity: {fifo_entry.remaining_quantity}")
            else:
                print(f"  - WARNING: No source_fifo_id recorded for this reservation!")

        success, message = POSIntegrationService.release_reservation(order_id)
        print(f"DEBUG: Release result - Success: {success}, Message: {message}")

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        print(f"DEBUG: Exception in release_reservation: {str(e)}")
        import traceback
        traceback.print_exc()
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