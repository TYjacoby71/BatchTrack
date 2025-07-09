from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from flask_login import current_user
from sqlalchemy import func, and_

from ..models import db, InventoryItem, InventoryHistory, Reservation
from .inventory_adjustment import process_inventory_adjustment
from app.blueprints.fifo.services import FIFOService

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

            # 4. LOG the reservation in FIFO for audit (no remaining_quantity)
            FIFOService.add_fifo_entry(
                inventory_item_id=reserved_item.id,
                quantity=quantity,
                change_type='reserved_allocation',
                unit=original_item.unit,
                notes=f"Reserved for order {order_id} from batch. {notes or ''}",
                cost_per_unit=original_item.cost_per_unit,
                created_by=current_user.id if current_user.is_authenticated else None,
                order_id=order_id,
                source=source,
                fifo_reference_id=source_fifo_id
            )

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

            # Find active reservations for this order
            active_reservations = Reservation.query.filter(
                and_(
                    Reservation.order_id == order_id,
                    Reservation.status == 'active'
                )
            ).all()

            print(f"DEBUG POS: Found {len(active_reservations)} active reservations")

            if not active_reservations:
                return False, f"No active reservations found for order {order_id}"

            total_released = 0.0

            for i, reservation in enumerate(active_reservations):
                print(f"DEBUG POS: Processing reservation {i+1}")
                print(f"DEBUG POS: Reservation ID: {reservation.id}")
                print(f"DEBUG POS: Reserved Item: {reservation.reserved_item}")
                print(f"DEBUG POS: Source FIFO ID: {reservation.source_fifo_id}")

                if reservation.reserved_item:
                    # Mark reservation as released
                    reservation.mark_released()
                    print(f"DEBUG POS: Marked reservation as released")

                    # Credit back to ORIGINAL product's FIFO history
                    reserved_item = reservation.reserved_item
                    original_product_item = reservation.product_item

                    # 1. Log the release in reserved item FIFO (for audit)
                    print(f"DEBUG POS: Adding FIFO entry for reserved item release")
                    try:
                        FIFOService.add_fifo_entry(
                            inventory_item_id=reserved_item.id,
                            quantity=-reservation.quantity,
                            change_type='unreserved',
                            unit=reservation.unit,
                            notes=f"Released reservation for order {order_id}",
                            cost_per_unit=reservation.unit_cost,
                            created_by=current_user.id if current_user.is_authenticated else None,
                            order_id=order_id,
                            fifo_reference_id=reservation.source_fifo_id
                        )
                        print(f"DEBUG POS: Reserved item FIFO entry added successfully")
                    except Exception as fifo_error:
                        print(f"DEBUG POS: Error adding reserved item FIFO entry: {str(fifo_error)}")
                        raise fifo_error

                    # 2. Credit back to ORIGINAL source lot using proper service
                    if original_product_item and original_product_item.type == 'product' and reservation.source_fifo_id:
                        print(f"DEBUG POS: Using inventory adjustment service to credit back to source lot")
                        try:
                            success = process_inventory_adjustment(
                                item_id=original_product_item.id,
                                quantity=reservation.quantity,
                                change_type='unreserved',
                                unit=reservation.unit,
                                notes=f"Credited back from released reservation for order {order_id}",
                                created_by=current_user.id if current_user.is_authenticated else None,
                                item_type='product',
                                order_id=order_id
                            )
                            
                            if not success:
                                raise Exception("Failed to credit back to source via inventory adjustment")
                            
                            print(f"DEBUG POS: Successfully credited back to source lot via inventory adjustment service")
                        except Exception as adj_error:
                            print(f"DEBUG POS: Error crediting back via inventory adjustment: {str(adj_error)}")
                            raise adj_error

                    total_released += reservation.quantity
                    print(f"DEBUG POS: Total released so far: {total_released}")
                else:
                    print(f"DEBUG POS: WARNING - No reserved_item found for reservation {reservation.id}")

            print(f"DEBUG POS: Committing database changes")
            db.session.commit()
            print(f"DEBUG POS: Success - Released {total_released} units")
            return True, f"Released {total_released} units for order {order_id}"

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

                # Create sale entry for audit trail (no remaining_quantity)
                FIFOService.add_fifo_entry(
                    inventory_item_id=reserved_item.id,
                    quantity=-reservation.quantity,
                    change_type='sale',
                    unit=reservation.unit,
                    notes=f"Sale confirmed for order {order_id}. {notes or ''}",
                    cost_per_unit=reservation.unit_cost,
                    created_by=current_user.id if current_user.is_authenticated else None,
                    order_id=order_id,
                    fifo_reference_id=reservation.source_fifo_id
                )

                total_sold += reservation.quantity

            db.session.commit()
            return True, f"Confirmed sale of {total_sold} units for order {order_id}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error confirming sale: {str(e)}"

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