from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from flask_login import current_user
from sqlalchemy import func, and_

from ..models import db, InventoryItem, InventoryHistory
from .inventory_adjustment import process_inventory_adjustment
from app.blueprints.fifo.services import FIFOService

class POSIntegrationService:
    """Service for integrating with POS systems like Shopify, Etsy, etc."""

    @staticmethod
    def reserve_inventory(item_id: int, quantity: float, order_id: str, source: str = "shopify", notes: str = None) -> tuple[bool, str]:
        """
        Reserve inventory using FIFO-aware batch tracking
        Args:
            item_id: Inventory item ID (product type)
            quantity: Quantity to reserve
            order_id: Order identifier (required)
            source: Source system ("shopify", "manual", etc.)
            notes: Optional notes

        Returns:
            (success, message)
        """
        try:
            # Get the original inventory item
            original_item = InventoryItem.query.get(item_id)
            if not original_item or original_item.type != 'product':
                return False, "Product item not found"

            # Check if we have enough available inventory
            available = original_item.quantity
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

            # Get the oldest available FIFO entry to reserve from
            from app.blueprints.fifo.services import FIFOService
            fifo_entries = FIFOService.get_fifo_entries(item_id)
            
            if not fifo_entries:
                return False, "No FIFO entries available for reservation"

            # Find the FIFO entry to reserve from (first with sufficient quantity)
            source_fifo_id = None
            for entry in fifo_entries:
                if entry.remaining_quantity >= quantity:
                    source_fifo_id = entry.id
                    break
            
            if not source_fifo_id:
                # Try to reserve from multiple entries
                source_fifo_id = fifo_entries[0].id

            # Deduct from original item using FIFO
            original_success = process_inventory_adjustment(
                item_id=item_id,
                quantity=quantity,
                change_type='reserved',
                notes=f"Reserved for order {order_id} ({source}). {notes or ''}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if not original_success:
                return False, "Failed to deduct from available inventory"

            # Create reservation entry in reserved item with FIFO reference
            reservation_success = FIFOService.add_fifo_entry(
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

            if not reservation_success:
                # Rollback the original deduction
                process_inventory_adjustment(
                    item_id=item_id,
                    quantity=quantity,
                    change_type='unreserved',
                    notes=f"Rollback failed reservation for order {order_id}",
                    order_id=order_id,
                    created_by=current_user.id if current_user.is_authenticated else None
                )
                return False, "Failed to create reservation entry"

            # Update reserved item quantity
            reserved_item.quantity += quantity

            db.session.commit()
            return True, f"Reserved {quantity} units for order {order_id} from batch"

        except Exception as e:
            db.session.rollback()
            return False, f"Error reserving inventory: {str(e)}"

    @staticmethod
    def release_reservation(order_id: str) -> tuple[bool, str]:
        """
        Release all reservations for an order, crediting back to original batch/lot
        Args:
            order_id: Order identifier to release

        Returns:
            (success, message)
        """
        try:
            # Find all reserved allocations for this order
            from app.models.product import ProductSKUHistory
            
            reserved_entries = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.change_type == 'reserved_allocation',
                    ProductSKUHistory.order_id == order_id,
                    ProductSKUHistory.remaining_quantity > 0
                )
            ).all()

            if not reserved_entries:
                return False, f"No active reservations found for order {order_id}"

            total_released = 0
            for entry in reserved_entries:
                reserved_item = InventoryItem.query.get(entry.inventory_item_id)
                if not reserved_item or reserved_item.type != 'product-reserved':
                    continue

                # Find the original product item
                original_name = reserved_item.name.replace(" (Reserved)", "")
                original_item = InventoryItem.query.filter_by(
                    name=original_name,
                    type='product',
                    organization_id=reserved_item.organization_id
                ).first()

                if not original_item:
                    continue

                quantity_to_release = entry.remaining_quantity

                # Mark the reservation as released (set remaining_quantity to 0)
                entry.remaining_quantity = 0

                # Credit back to the original FIFO entry if it exists
                if entry.fifo_reference_id:
                    original_fifo_entry = ProductSKUHistory.query.get(entry.fifo_reference_id)
                    if original_fifo_entry:
                        original_fifo_entry.remaining_quantity += quantity_to_release

                # Update inventory quantities
                reserved_item.quantity -= quantity_to_release
                original_item.quantity += quantity_to_release

                # Log the release
                from app.blueprints.fifo.services import FIFOService
                FIFOService.add_fifo_entry(
                    inventory_item_id=reserved_item.id,
                    quantity=-quantity_to_release,
                    change_type='unreserved',
                    unit=entry.unit,
                    notes=f"Released reservation for order {order_id}",
                    cost_per_unit=entry.unit_cost,
                    created_by=current_user.id if current_user.is_authenticated else None,
                    order_id=order_id,
                    fifo_reference_id=entry.fifo_reference_id
                )

                total_released += quantity_to_release

            db.session.commit()
            return True, f"Released {total_released} units for order {order_id}, credited back to original batches"

        except Exception as e:
            db.session.rollback()
            return False, f"Error releasing reservation: {str(e)}"

    @staticmethod
    def confirm_sale(order_id: str, notes: str = None) -> Tuple[bool, str]:
        """
        Convert reservation to actual sale (Shopify fulfillment webhook)
        """
        try:
            from app.models.product import ProductSKUHistory
            
            # Find active reservations for this order
            reservations = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.order_id == order_id,
                    ProductSKUHistory.change_type == 'reserved_allocation',
                    ProductSKUHistory.remaining_quantity > 0
                )
            ).all()

            if not reservations:
                return False, "No active reservations found for this order"

            total_sold = 0
            for reservation in reservations:
                reserved_item = InventoryItem.query.get(reservation.inventory_item_id)
                if not reserved_item or reserved_item.type != 'product-reserved':
                    continue

                quantity_sold = reservation.remaining_quantity

                # Mark reservation as consumed (set remaining_quantity to 0)
                reservation.remaining_quantity = 0

                # Update reserved inventory quantity
                reserved_item.quantity -= quantity_sold

                # Create sale entry for audit trail
                from app.blueprints.fifo.services import FIFOService
                FIFOService.add_fifo_entry(
                    inventory_item_id=reserved_item.id,
                    quantity=-quantity_sold,
                    change_type='sale',
                    unit=reservation.unit,
                    notes=f"Sale confirmed for order {order_id}. {notes or ''}",
                    cost_per_unit=reservation.unit_cost,
                    created_by=current_user.id if current_user.is_authenticated else None,
                    order_id=order_id,
                    fifo_reference_id=reservation.fifo_reference_id
                )

                total_sold += quantity_sold

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
        expired = InventoryHistory.query.filter(
            and_(
                InventoryHistory.change_type == 'reserved',
                InventoryHistory.is_reserved == True,
                InventoryHistory.expiration_date < datetime.utcnow()
            )
        ).all()

        count = 0
        for reservation in expired:
            success, _ = POSIntegrationService.release_reservation(reservation.order_id)
            if success:
                count += 1

        return count

    @staticmethod
    def get_available_quantity(item_id: int) -> float:
        """
        Get available quantity for POS systems
        """
        item = InventoryItem.query.get(item_id)
        if not item:
            return 0.0
        return item.calculated_available_quantity

    @staticmethod
    def process_damage_return_fifo(item_id: int, damage_qty: float, return_qty: float, notes: str = None):
        """
        Process damage and return in FIFO order automatically
        Args:
            item_id: Inventory item ID
            damage_qty: Quantity damaged (will be deducted from oldest FIFO)
            return_qty: Quantity returned (will be added to newest FIFO or create new)
            notes: Optional notes
        """
        try:
            # Process damage first (FIFO deduction)
            if damage_qty > 0:
                process_inventory_adjustment(
                    item_id=item_id,
                    quantity=damage_qty,
                    change_type='damaged',
                    notes=f"Damaged goods. {notes or ''}",
                    created_by=current_user.id if current_user.is_authenticated else None
                )

            # Process return (add back to inventory)
            if return_qty > 0:
                process_inventory_adjustment(
                    item_id=item_id,
                    quantity=return_qty,
                    change_type='manual_addition',  # Creates new FIFO entry
                    notes=f"Returned goods. {notes or ''}",
                    created_by=current_user.id if current_user.is_authenticated else None
                )

            return True, "Damage and return processed successfully"

        except Exception as e:
            db.session.rollback()
            return False, str(e)