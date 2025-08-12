from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import current_user, login_required
from ...models import db, InventoryItem
from ...models.product import ProductSKU
from ...models.reservation import Reservation
from ...services.pos_integration import POSIntegrationService
from app.services.inventory_adjustment import record_audit_entry as _record_audit_entry
import logging

# This function is intended for test usage and has a different signature.
# The API usage is handled by the second _write_unreserved_audit function below.
def _write_unreserved_audit(reservation):
    """Wrapper for audit entry - used by tests"""
    return _record_audit_entry(
        item_id=reservation.inventory_item_id,
        change_type="unreserved",
        note=f"Reservation {reservation.id} released",
        item_type="product",
        fifo_reference_id=reservation.source_fifo_id,
    )

# This is the helper function for API audit entries and its signature is corrected.
def _write_unreserved_audit(item_id, unit, notes):
    """Wrapper for audit entry - used by tests"""
    return _record_audit_entry(
        item_id=item_id,
        quantity=0,  # No quantity change for audit entry
        change_type="unreserved_audit",
        notes=f"Unreserved via API: {notes}"
    )

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
        # Use ReservationService to release the reservation
        success = ReservationService.release_reservation(reservation_id)

        if success:
            db.session.commit()
            # Use the helper function to write the audit entry
            reservation = Reservation.query.get(reservation_id)
            if reservation:
                # Calling the test-specific wrapper function here as per original code structure
                _write_unreserved_audit(reservation)
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

        # Create sale audit entry using canonical service (reservation already deducted inventory)
        record_audit_entry(
            item_id=reservation.product_item_id,
            change_type='sale_from_reservation',
            notes=f"Sale from reservation {reservation.order_id}",
            unit=reservation.unit
        )

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
    from app.services.inventory_adjustment import record_audit_entry # Import for audit logging

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
            # Use ReservationService to release the reservation
            success = ReservationService.release_reservation(reservation.id)
            if success:
                reservation.mark_expired()
                count += 1
            else:
                # Log failure to release reservation, but continue expiring others
                logger.warning(f"Failed to release reservation {reservation.id} during expiration process.")


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