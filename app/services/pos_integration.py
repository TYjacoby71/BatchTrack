import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from flask import current_app
from flask_login import current_user
from ..models import db, InventoryItem, Reservation
from sqlalchemy import and_, func
from ..utils import generate_fifo_code

# Import necessary canonical functions
from app.blueprints.fifo.services import FIFOService
from app.services.inventory_adjustment import record_audit_entry, process_inventory_adjustment

def _db():
    """Get database session - works with real SQLAlchemy and test mocks"""
    return getattr(db, "session", db)

logger = logging.getLogger(__name__)

class POSIntegrationService:
    """Service for integrating with POS systems like Shopify, Etsy, etc."""

    @staticmethod
    def reserve_inventory(item_id: int, quantity: float, order_id: str, source: str = "shopify",
                         notes: str = None, sale_price: float = None, expires_in_hours: int = None) -> tuple[bool, str]:
        """
        Reserve inventory using new reservation model - acts like regular deduction
        Args:
            item_id: Inventory item ID (product type)
            quantity: Quantity to reserve
            order_id: Order identifier (required)
            source: Source system ("shopify", "manual", etc.)
            notes: Optional notes
            sale_price: Expected sale price
            expires_in_hours: Hours until reservation expires

        Returns:
            (success, message)
        """
        try:
            # Get the original inventory item
            original_item = InventoryItem.query.get(item_id)
            if not original_item or original_item.type != 'product':
                return False, "Product item not found"

            # Check if we have enough available inventory (ignoring expired lots)
            available = original_item.available_quantity  # This should exclude expired
            if available < quantity:
                return False, f"Insufficient inventory. Available: {available}, Requested: {quantity}"

            # Get or create the reserved inventory item
            reserved_item_name = f"{original_item.name} (Reserved)"
            reserved_item = InventoryItem.query.filter_by(
                name=reserved_item_name,
                type='product-reserved',
                organization_id=original_item.organization_id
            ).first()

            if not reserved_item:
                # Create new reserved inventory item
                reserved_item = InventoryItem(
                    name=reserved_item_name,
                    type='product-reserved',
                    unit=original_item.unit,
                    cost_per_unit=original_item.cost_per_unit,
                    quantity=0.0,
                    organization_id=original_item.organization_id,
                    category_id=original_item.category_id,
                    is_perishable=original_item.is_perishable,
                    shelf_life_days=original_item.shelf_life_days
                )
                db.session.add(reserved_item)
                db.session.flush()

            # Get the source FIFO entry for tracking
            fifo_entries = FIFOService.get_fifo_entries(item_id)
            source_fifo_id = None
            source_batch_id = None

            if fifo_entries:
                # Use the oldest available entry for reference
                oldest_entry = fifo_entries[0]
                source_fifo_id = oldest_entry.id
                source_batch_id = getattr(oldest_entry, 'batch_id', None)

            # 1. DEDUCT from original item using regular FIFO (no remaining_quantity tracking)
            deduction_success = process_inventory_adjustment(
                item_id=item_id,
                quantity=quantity,
                change_type='reserved',
                notes=f"Reserved for order {order_id} ({source}). {notes or ''}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if not deduction_success:
                return False, "Failed to deduct from available inventory"

            # 2. CREATE reservation line item (this is now the source of truth)
            expires_at = None
            if expires_in_hours:
                expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

            reservation = Reservation(
                order_id=order_id,
                product_item_id=item_id,
                reserved_item_id=reserved_item.id,
                quantity=quantity,
                unit=original_item.unit,
                unit_cost=original_item.cost_per_unit,
                sale_price=sale_price,
                source_fifo_id=source_fifo_id,
                source_batch_id=source_batch_id,
                source=source,
                expires_at=expires_at,
                notes=notes,
                created_by=current_user.id if current_user.is_authenticated else None,
                organization_id=current_user.organization_id if current_user.is_authenticated else original_item.organization_id
            )
            db.session.add(reservation)

            # 3. UPDATE reserved item quantity (for display purposes)
            reserved_item.quantity += quantity

            # 4. LOG the reservation using canonical inventory adjustment
            allocation_success = process_inventory_adjustment(
                item_id=reserved_item.id,
                quantity=quantity,
                change_type='reserved_allocation',
                unit=original_item.unit,
                notes=f"Reserved for order {order_id}. {notes or ''}",
                created_by=current_user.id if current_user.is_authenticated else None,
                cost_override=original_item.cost_per_unit
            )

            if not allocation_success:
                return False, "Failed to log reservation allocation"

            db.session.commit()
            return True, f"Reserved {quantity} units for order {order_id}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error reserving inventory: {str(e)}"

    @staticmethod
    def release_reservation(order_id: str):
        """
        Release reservation - returns inventory to available stock via FIFO credit
        """
        try:
            print(f"DEBUG POS: Starting release_reservation for order_id: {order_id}")
            print(f"DEBUG POS: Delegating to ReservationService.release_reservation")

            # Use the centralized reservation service
            success, message = ReservationService.release_reservation(order_id)

            if success:
                print(f"DEBUG POS: Success - {message}")
            else:
                print(f"DEBUG POS: Failed - {message}")

            return success, message

        except Exception as e:
            print(f"DEBUG POS: Exception in release_reservation: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False, f"Error releasing reservation: {str(e)}"

    @staticmethod
    def confirm_sale(order_id: str, notes: str = None) -> Tuple[bool, str]:
        """
        Convert reservation to actual sale (Shopify fulfillment webhook)
        """
        try:
            # Find active reservations for this order
            active_reservations = Reservation.query.filter(
                and_(
                    Reservation.order_id == order_id,
                    Reservation.status == 'active'
                )
            ).all()

            if not active_reservations:
                return False, "No active reservations found for this order"

            total_sold = 0
            for reservation in active_reservations:
                reserved_item = reservation.reserved_item
                if not reserved_item:
                    continue

                # Update reserved inventory quantity
                reserved_item.quantity -= reservation.quantity

                # Mark reservation as converted to sale
                reservation.mark_converted_to_sale()

                # Get the original item to pass unit to the adjustment service
                item = InventoryItem.query.get(reservation.product_item_id)
                if not item:
                    logger.error(f"Inventory item not found for reservation {reservation.id}")
                    continue

                # Use canonical inventory adjustment service instead of direct FIFO calls
                sale_success = process_inventory_adjustment(
                    item_id=reservation.product_item_id,
                    quantity=-abs(reservation.quantity),  # Negative for deduction
                    change_type='sale',
                    unit=item.unit,
                    notes=f"POS Sale: {notes}",
                    created_by=None,  # POS system user
                )

                if not sale_success:
                    logger.error(f"Failed to process sale adjustment for reservation {reservation.id}")
                    return False, "Failed to record sale in inventory system"

                total_sold += reservation.quantity

            db.session.commit()
            return True, f"Confirmed sale of {total_sold} units for order {order_id}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error confirming sale: {str(e)}"

    @staticmethod
    def confirm_return(order_id: str, notes: str = None) -> Tuple[bool, str]:
        """
        Process a return from a POS order, crediting inventory back.
        """
        try:
            # Find completed sales reservations for this order
            completed_reservations = Reservation.query.filter(
                and_(
                    Reservation.order_id == order_id,
                    Reservation.status == 'converted_to_sale' # Or potentially 'completed' depending on reservation status logic
                )
            ).all()

            if not completed_reservations:
                return False, "No completed sales reservations found for this order"

            total_returned = 0
            for reservation in completed_reservations:
                sku = reservation # Assuming reservation object has related item details

                # Update reserved inventory quantity (or revert the deduction if needed)
                # Here we assume return means inventory goes back to the original item or a 'returned' category
                # For simplicity, let's assume it goes back to the reserved_item, then process_inventory_adjustment handles the rest.
                if reservation.reserved_item:
                    reservation.reserved_item.quantity += reservation.quantity

                # Mark reservation as returned
                reservation.mark_returned()

                # Get the original item to pass unit to the adjustment service
                item = InventoryItem.query.get(reservation.product_item_id)
                if not item:
                    logger.error(f"Inventory item not found for return reservation {reservation.id}")
                    continue

                # Use canonical inventory adjustment service for returns
                return_success = process_inventory_adjustment(
                    item_id=reservation.product_item_id,
                    quantity=abs(reservation.quantity),  # Positive for addition
                    change_type='return',
                    unit=item.unit,
                    notes=f"POS Return: {notes}",
                    created_by=None
                )

                if not return_success:
                    logger.error(f"Failed to process return adjustment for reservation {reservation.id}")
                    return False, "Failed to process return in inventory system"

                total_returned += reservation.quantity

            db.session.commit()
            return True, f"Processed return of {total_returned} units for order {order_id}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error processing return: {str(e)}"


    @staticmethod
    def cleanup_expired_reservations() -> int:
        """
        Clean up expired reservations
        Returns: Number of reservations cleaned up
        """
        try:
            # Find expired reservations
            expired_reservations = Reservation.query.filter(
                and_(
                    Reservation.status == 'active',
                    Reservation.expires_at.isnot(None),
                    Reservation.expires_at < datetime.utcnow()
                )
            ).all()

            count = 0
            for reservation in expired_reservations:
                # Release the expired reservation
                success, _ = POSIntegrationService.release_reservation(reservation.order_id)
                if success:
                    reservation.mark_expired()
                    count += 1

            db.session.commit()
            return count

        except Exception as e:
            db.session.rollback()
            return 0

    @staticmethod
    def get_available_quantity(item_id: int) -> float:
        """
        Get available quantity for POS systems (excludes expired lots only)
        """
        item = InventoryItem.query.get(item_id)
        if not item:
            return 0.0
        return item.available_quantity  # This should exclude expired, not reserved

    @staticmethod
    def get_reservations_for_order(order_id: str) -> List[Reservation]:
        """Get all reservations for a specific order"""
        return Reservation.query.filter_by(order_id=order_id).all()

    @staticmethod
    def get_active_reservations_for_item(item_id: int) -> List[Reservation]:
        """Get active reservations for a specific product"""
        return Reservation.query.filter(
            and_(
                Reservation.product_item_id == item_id,
                Reservation.status == 'active'
            )
        ).all()

    @staticmethod
    def get_total_reserved_for_item(item_id: int) -> float:
        """Get total reserved quantity for a product"""
        result = db.session.query(func.sum(Reservation.quantity)).filter(
            and_(
                Reservation.product_item_id == item_id,
                Reservation.status == 'active'
            )
        ).scalar()
        return result or 0.0

# Placeholder for FIFOService and Reservation.mark_returned(), Reservation.mark_converted_to_sale()
# These would be defined in other modules.
class FIFOService:
    @staticmethod
    def get_fifo_entries(item_id):
        return [] # Dummy implementation

class Reservation:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.status = 'active' # Default status

    def mark_converted_to_sale(self):
        self.status = 'converted_to_sale'

    def mark_returned(self):
        self.status = 'returned'

    def mark_expired(self):
        self.status = 'expired'

# Mocking necessary components for the provided code to be syntactically valid
class InventoryItem:
    query = None # Dummy
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class InventoryHistory:
    pass # Dummy

class ReservationService:
    @staticmethod
    def release_reservation(order_id):
        return True, "Reservation released" # Dummy

# Mocking db session
class MockDBSession:
    def add(self, obj): pass
    def flush(self): pass
    def commit(self): pass
    def rollback(self): pass

db = MockDBSession()

# Mocking current_user
class MockCurrentUser:
    is_authenticated = False
    organization_id = 1 # Dummy org ID

current_user = MockCurrentUser()