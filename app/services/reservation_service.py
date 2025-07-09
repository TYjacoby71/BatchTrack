from flask import current_app
from flask_login import current_user
from ..models import db, InventoryItem, Reservation
from sqlalchemy import and_, func
from ..utils import generate_fifo_code

class ReservationService:
    """Service for managing product reservations - ONLY handles products, never raw inventory"""

    @staticmethod
    def create_reservation(inventory_item_id, quantity, order_id, source_fifo_id, unit_cost, customer=None, sale_price=None, notes="", source="manual"):
        """
        Create a new product reservation by deducting from specific FIFO lot
        This should only be called AFTER FIFO deduction has been calculated and executed
        """
        from app.models.product import ProductSKUHistory

        product_item = InventoryItem.query.get(inventory_item_id)
        if not product_item or product_item.type != 'product':
            return None, "Item is not a product or not found"

        # Get or create reserved item
        reserved_item = ReservationService.get_reserved_item_for_product(inventory_item_id)
        if not reserved_item:
            return None, "Failed to get or create reserved item"

        # Create the reservation record tracking the FIFO source
        reservation = Reservation(
            product_item_id=inventory_item_id,
            reserved_item_id=reserved_item.id,
            quantity=quantity,
            unit=product_item.unit,
            unit_cost=unit_cost,
            sale_price=sale_price,
            order_id=order_id,
            customer=customer,
            source=source,
            status='active',
            notes=notes,
            source_fifo_id=source_fifo_id,  # Track which FIFO lot this came from
            created_by=current_user.id if current_user.is_authenticated else None,
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )
        db.session.add(reservation)

        # Update reserved item quantity
        reserved_item.quantity += quantity

        return reservation, None

    @staticmethod
    def release_reservation(order_id):
        """
        Release reservations by crediting back to original FIFO lots
        This is the ONLY method that should handle unreserved operations
        """
        from app.models.product import ProductSKUHistory

        # Find active reservations for this order
        reservations = Reservation.query.filter_by(
            order_id=order_id,
            status='active'
        ).all()

        if not reservations:
            return False, f"No active reservations found for order {order_id}"

        total_released = 0

        for reservation in reservations:
            # Validate this is a product reservation
            if not reservation.product_item or reservation.product_item.type != 'product':
                continue

            # Find the original ProductSKUHistory entry to credit back to
            source_entry = ProductSKUHistory.query.get(reservation.source_fifo_id)
            if not source_entry:
                print(f"Warning: Source FIFO entry {reservation.source_fifo_id} not found for reservation")
                continue

            # Credit back to the original lot's remaining_quantity
            source_entry.remaining_quantity += reservation.quantity
            print(f"Credited {reservation.quantity} back to lot {reservation.source_fifo_id}")

            # Create ProductSKUHistory entry showing the credit back
            credit_entry = ProductSKUHistory(
                inventory_item_id=reservation.product_item_id,
                quantity_change=reservation.quantity,  # POSITIVE - adding back
                remaining_quantity=0,  # This is an audit entry, not a FIFO lot
                change_type='unreserved',
                unit=reservation.unit,
                unit_cost=reservation.unit_cost,
                notes=f"Released reservation - credited back to lot {reservation.source_fifo_id}",
                created_by=current_user.id if current_user.is_authenticated else None,
                order_id=order_id,
                fifo_reference_id=reservation.source_fifo_id,
                fifo_code=generate_fifo_code(),
                organization_id=current_user.organization_id if current_user.is_authenticated else None
            )
            db.session.add(credit_entry)

            # Update inventory item quantity
            reservation.product_item.quantity += reservation.quantity

            # Update reserved item quantity
            reservation.reserved_item.quantity -= reservation.quantity

            # Mark reservation as released
            reservation.mark_released()

            total_released += reservation.quantity

        try:
            db.session.commit()
            return True, f"Released {total_released} units for order {order_id}"
        except Exception as e:
            db.session.rollback()
            return False, f"Error releasing reservations: {str(e)}"

    @staticmethod
    def cancel_reservation(reservation_id):
        """Cancel an existing product reservation"""
        reservation = Reservation.query.get(reservation_id)
        if not reservation:
            return False, "Reservation not found"

        if reservation.status != 'active':
            return False, "Reservation is not active"

        product_item = reservation.product_item
        reserved_item = reservation.reserved_item

        if not product_item or not reserved_item:
            return False, "Product or Reserved item not found"

        # Adjust quantities (revert the reservation)
        product_item.quantity += reservation.quantity
        reserved_item.quantity -= reservation.quantity

        # Update the reservation status
        reservation.status = 'cancelled'

        # Record the transaction in inventory history
        history_entry = InventoryHistory(
            inventory_item_id=product_item.id,
            change_type='reservation_cancellation',
            quantity_change=reservation.quantity,
            remaining_quantity=product_item.quantity,
            unit=product_item.unit,
            note=f"Cancelled reservation {reservation_id} for order {reservation.order_id}",
            created_by=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(history_entry)

        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def fulfill_reservation(reservation_id):
        """Mark a product reservation as fulfilled"""
        reservation = Reservation.query.get(reservation_id)
        if not reservation:
            return False, "Reservation not found"

        if reservation.status != 'active':
            return False, "Reservation is not active"

        reserved_item = reservation.reserved_item
        if not reserved_item:
            return False, "Reserved item not found"

        # Adjust reserved item quantity
        reserved_item.quantity -= reservation.quantity

        # Update reservation status
        reservation.status = 'fulfilled'

        # Record the transaction in inventory history
        history_entry = InventoryHistory(
            inventory_item_id=reserved_item.id,
            change_type='reservation_fulfillment',
            quantity_change=-reservation.quantity,
            remaining_quantity=reserved_item.quantity,
            unit=reserved_item.unit,
            note=f"Fulfilled reservation {reservation_id} for order {reservation.order_id}",
            created_by=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(history_entry)

        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_reserved_item_for_product(product_item_id):
        """Get or create the reserved inventory item for a product"""
        product_item = InventoryItem.query.get(product_item_id)
        if not product_item:
            return None

        reserved_name = f"{product_item.name} (Reserved)"
        reserved_item = InventoryItem.query.filter_by(
            name=reserved_name,
            type='product-reserved',
            organization_id=product_item.organization_id
        ).first()

        if not reserved_item:
            reserved_item = InventoryItem(
                name=reserved_name,
                type='product-reserved',
                unit=product_item.unit,
                cost_per_unit=product_item.cost_per_unit,
                quantity=0.0,
                organization_id=product_item.organization_id,
                category_id=product_item.category_id,
                is_perishable=product_item.is_perishable,
                shelf_life_days=product_item.shelf_life_days
            )
            db.session.add(reserved_item)
            db.session.flush()

        return reserved_item

    @staticmethod
    def get_product_item_for_reserved(reserved_item_id):
        """Get the original product item from a reserved item"""
        reserved_item = InventoryItem.query.get(reserved_item_id)
        if not reserved_item or reserved_item.type != 'product-reserved':
            return None

        original_name = reserved_item.name.replace(" (Reserved)", "")
        product_item = InventoryItem.query.filter_by(
            name=original_name,
            type='product',
            organization_id=reserved_item.organization_id
        ).first()

        return product_item

    @staticmethod
    def get_total_inventory_for_sku(sku):
        """Get combined available + reserved quantities for a SKU"""
        if not sku.inventory_item:
            return 0.0

        # Get available quantity (excludes expired)
        available_qty = sku.inventory_item.available_quantity

        # Get reserved quantity from active reservations
        reserved_qty = ReservationService.get_total_reserved_for_item(sku.inventory_item.id)

        return available_qty + reserved_qty

    @staticmethod
    def get_total_reserved_for_item(item_id):
        """Get total reserved quantity for a product from active reservations"""
        result = db.session.query(func.sum(Reservation.quantity)).filter(
            and_(
                Reservation.product_item_id == item_id,
                Reservation.status == 'active'
            )
        ).scalar()
        return result or 0.0

    @staticmethod
    def get_reservation_summary_for_sku(sku):
        """Get reservation summary for display in SKU view"""
        if not sku.inventory_item:
            return {
                'available': 0.0,
                'reserved': 0.0,
                'total': 0.0,
                'reservations': []
            }

        available_qty = sku.inventory_item.available_quantity

        # Get active reservations grouped by order
        active_reservations = Reservation.query.filter(
            and_(
                Reservation.product_item_id == sku.inventory_item.id,
                Reservation.status == 'active'
            )
        ).all()

        # Group by order_id for display
        order_reservations = {}
        total_reserved = 0.0

        for reservation in active_reservations:
            order_id = reservation.order_id
            if order_id not in order_reservations:
                order_reservations[order_id] = {
                    'order_id': order_id,
                    'quantity': 0.0,
                    'created_at': reservation.created_at,
                    'expires_at': reservation.expires_at,
                    'source': reservation.source,
                    'sale_price': reservation.sale_price
                }
            order_reservations[order_id]['quantity'] += reservation.quantity
            total_reserved += reservation.quantity

        reservations = list(order_reservations.values())

        return {
            'available': available_qty,
            'reserved': total_reserved,
            'total': available_qty + total_reserved,
            'reservations': reservations
        }

    @staticmethod
    def get_reservation_details_for_order(order_id):
        """Get detailed reservation information for an order"""
        reservations = Reservation.query.filter_by(order_id=order_id).all()

        details = []
        for reservation in reservations:
            details.append({
                'id': reservation.id,
                'product_name': reservation.product_item.name if reservation.product_item else 'Unknown',
                'quantity': reservation.quantity,
                'unit': reservation.unit,
                'unit_cost': reservation.unit_cost,
                'sale_price': reservation.sale_price,
                'status': reservation.status,
                'created_at': reservation.created_at,
                'expires_at': reservation.expires_at,
                'source': reservation.source,
                'source_batch_id': reservation.source_batch_id
            })

        return details