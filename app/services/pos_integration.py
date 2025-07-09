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
    def reserve_inventory(item_id: int, quantity: float, order_id: str, notes: str = None) -> tuple[bool, str]:
        """
        Reserve inventory for pending orders using separate reserved inventory item
        Args:
            item_id: Inventory item ID
            quantity: Quantity to reserve
            order_id: Order identifier
            notes: Optional notes

        Returns:
            (success, message)
        """
        try:
            # Get the original inventory item
            original_item = InventoryItem.query.get(item_id)
            if not original_item:
                return False, "Item not found"

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

            # Deduct from original item
            original_success = process_inventory_adjustment(
                item_id=item_id,
                quantity=quantity,
                change_type='reserved',
                notes=f"Reserved for order {order_id}. {notes or ''}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if not original_success:
                return False, "Failed to deduct from available inventory"

            # Add to reserved item
            reserved_success = process_inventory_adjustment(
                item_id=reserved_item.id,
                quantity=quantity,
                change_type='reserved_allocation',
                notes=f"Reserved allocation for order {order_id}. {notes or ''}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if not reserved_success:
                # Rollback the original deduction
                process_inventory_adjustment(
                    item_id=item_id,
                    quantity=quantity,
                    change_type='unreserved',
                    notes=f"Rollback failed reservation for order {order_id}",
                    order_id=order_id,
                    created_by=current_user.id if current_user.is_authenticated else None
                )
                return False, "Failed to allocate to reserved inventory"

            db.session.commit()
            return True, f"Reserved {quantity} units for order {order_id}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error reserving inventory: {str(e)}"

    @staticmethod
    def release_reservation(order_id: str) -> tuple[bool, str]:
        """
        Release all reservations for an order by moving from reserved back to available
        Args:
            order_id: Order identifier to release

        Returns:
            (success, message)
        """
        # Find all reserved items for this order
        reserved_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.change_type == 'reserved_allocation',
                InventoryHistory.order_id == order_id,
                InventoryHistory.remaining_quantity > 0
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

            # Deduct from reserved item
            reserved_success = process_inventory_adjustment(
                item_id=reserved_item.id,
                quantity=quantity_to_release,
                change_type='unreserved',
                notes=f"Released reservation for order {order_id}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if not reserved_success:
                continue

            # Add back to original item
            original_success = process_inventory_adjustment(
                item_id=original_item.id,
                quantity=quantity_to_release,
                change_type='unreserved',
                notes=f"Released reservation for order {order_id}",
                order_id=order_id,
                created_by=current_user.id if current_user.is_authenticated else None
            )

            if original_success:
                total_released += quantity_to_release

        db.session.commit()
        return True, f"Released {total_released} units for order {order_id}"

    @staticmethod
    def confirm_sale(order_id: str, notes: str = None) -> Tuple[bool, str]:
        """
        Confirm a sale (convert reservation to actual sale)
        """
        reservations = InventoryHistory.query.filter(
            and_(
                InventoryHistory.order_id == order_id,
                InventoryHistory.change_type == 'reserved',
                InventoryHistory.is_reserved == True
            )
        ).all()

        if not reservations:
            return False, "No active reservations found for this order"

        total_sold = 0
        for reservation in reservations:
            # Convert reservation to sale
            item = InventoryItem.query.get(reservation.inventory_item_id)
            if item:
                # Update inventory quantity (already deducted from FIFO)
                item.quantity -= abs(reservation.quantity_change)
                item.frozen_quantity -= abs(reservation.quantity_change)
                total_sold += abs(reservation.quantity_change)

                # Create sale history
                sale_history = InventoryHistory(
                    inventory_item_id=reservation.inventory_item_id,
                    change_type='sale',
                    quantity_change=reservation.quantity_change,  # Keep negative
                    unit=reservation.unit,
                    remaining_quantity=0,  # Sales don't create new FIFO entries
                    fifo_reference_id=reservation.fifo_reference_id,
                    unit_cost=reservation.unit_cost,
                    note=f"Sale confirmed for order {order_id}. {notes or ''}",
                    created_by=current_user.id if current_user.is_authenticated else None,
                    quantity_used=abs(reservation.quantity_change),  # Track actual consumption
                    order_id=order_id
                )
                db.session.add(sale_history)

            # Mark reservation as completed
            reservation.is_reserved = False
            reservation.note += " (Converted to sale)"

        db.session.commit()
        return True, f"Confirmed sale of {total_sold} units"

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