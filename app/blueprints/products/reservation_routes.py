import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import and_, desc

from ...models import Reservation
from ...models.product import ProductSKU
from ...services.pos_integration import POSIntegrationService
from ...services.reservation_view_service import ReservationViewService
from ...utils.permissions import require_permission

logger = logging.getLogger(__name__)


# No separate audit needed - all history goes through UnifiedInventoryHistory via FIFO operations

reservation_bp = Blueprint("reservation", __name__, url_prefix="/reservations")
reservations_bp = reservation_bp  # Keep backward compatibility alias


@reservations_bp.route("/")
@login_required
@require_permission("inventory.reserve")
def list_reservations():
    """List all reservations with filtering options"""
    status_filter = request.args.get("status", "active")
    order_id_filter = request.args.get("order_id", "")

    reservations = ReservationViewService.list_reservations(
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        order_id_filter=order_id_filter,
    )
    reservation_groups = ReservationViewService.build_reservation_groups(
        reservations=reservations
    )
    stats = ReservationViewService.build_stats(
        organization_id=current_user.organization_id
    )

    return render_template(
        "admin/reservations.html",
        reservation_groups=reservation_groups,
        stats=stats,
        status_filter=status_filter,
        order_id_filter=order_id_filter,
        current_time=ReservationViewService.utc_now(),
    )


@reservations_bp.route("/api/reservations/create", methods=["POST"])
@login_required
@require_permission("inventory.reserve")
def create_reservation():
    """Create a reservation for POS/order workflows.

    Accepts either:
    - item_id (inventory item id), or
    - sku_code (resolved to active org ProductSKU.inventory_item_id)
    """
    try:
        data = request.get_json(silent=True) or {}

        quantity_raw = data.get("quantity")
        order_id = (data.get("order_id") or "").strip()
        if quantity_raw is None or not order_id:
            return jsonify({"error": "Missing required fields: quantity, order_id"}), 400

        item_id = data.get("item_id")
        if item_id is None:
            sku_code = (data.get("sku_code") or "").strip()
            if not sku_code:
                return jsonify({"error": "Either item_id or sku_code is required"}), 400
            resolved_item_id = ReservationViewService.resolve_item_id_from_sku(
                sku_code=sku_code,
                organization_id=current_user.organization_id,
            )
            if not resolved_item_id:
                return jsonify({"error": "SKU not found or inactive"}), 404
            item_id = resolved_item_id

        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return jsonify({"error": "item_id must be an integer"}), 400

        try:
            quantity = float(quantity_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "quantity must be numeric"}), 400
        if quantity <= 0:
            return jsonify({"error": "quantity must be greater than 0"}), 400

        # Create the reservation
        success, message = POSIntegrationService.reserve_inventory(
            item_id=item_id,
            quantity=quantity,
            order_id=order_id,
            source=data.get("source", "manual"),
            notes=data.get("notes", ""),
            sale_price=data.get("sale_price"),
            expires_in_hours=data.get("expires_in_hours"),
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "inventory_item_id": item_id,
                    "order_id": order_id,
                }
            )
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:create_reservation",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@reservations_bp.route("/api/reservations/<order_id>/release", methods=["POST"])
@login_required
@require_permission("inventory.reserve")
def release_reservation(order_id):
    """Release a reservation by order ID"""
    try:
        logger.info("Releasing reservation(s) for order_id=%s", order_id)
        success, message = POSIntegrationService.release_reservation(order_id)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:release_reservation",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@reservations_bp.route("/api/reservations/<order_id>/confirm_sale", methods=["POST"])
@login_required
@require_permission("inventory.reserve")
def confirm_sale(order_id):
    """Convert reservation to sale"""
    try:
        data = request.get_json() or {}
        notes = data.get("notes", "")

        success, message = POSIntegrationService.confirm_sale(order_id, notes)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:248",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@reservations_bp.route("/api/reservations/<order_id>/details")
@login_required
@require_permission("inventory.reserve")
def get_reservation_details(order_id):
    """Get detailed information about a reservation"""
    try:
        from ...services.reservation_service import ReservationService

        details = ReservationService.get_reservation_details_for_order(order_id)
        return jsonify({"reservations": details})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:263",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@reservations_bp.route("/api/reservations/cleanup_expired", methods=["POST"])
@login_required
@require_permission("inventory.reserve")
def cleanup_expired():
    """Clean up expired reservations"""
    try:
        count = POSIntegrationService.cleanup_expired_reservations()
        return jsonify(
            {"success": True, "message": f"Cleaned up {count} expired reservations"}
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:278",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@reservations_bp.route("/api/inventory/<int:item_id>/reservations")
@login_required
@require_permission("inventory.reserve")
def get_item_reservations(item_id):
    """Get all reservations for a specific inventory item"""
    try:
        reservations = ReservationViewService.list_item_reservations(
            item_id=item_id,
            organization_id=current_user.organization_id,
        )
        return jsonify(
            {"reservations": ReservationViewService.serialize_item_reservations(reservations)}
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/reservation_routes.py:326",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500
