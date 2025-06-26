
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from flask_login import current_user
from sqlalchemy import func, and_

from ..models import db, InventoryItem, InventoryHistory
from .inventory_adjustment import process_inventory_adjustment, deduct_fifo

class POSIntegrationService:
    """Service for integrating with POS systems like Shopify, Etsy, etc."""
    
    @staticmethod
    def reserve_inventory(item_id: int, quantity: float, order_id: str, 
                         expiration_minutes: int = 30) -> Tuple[bool, str]:
        """
        Reserve inventory for an order (like adding to cart)
        Args:
            item_id: Inventory item ID
            quantity: Amount to reserve
            order_id: External order/cart ID
            expiration_minutes: How long to hold the reservation
        Returns:
            (success, message)
        """
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found"
        
        available = item.calculated_available_quantity
        if available < quantity:
            return False, f"Insufficient stock. Available: {available}, Requested: {quantity}"
        
        # Create reservation using FIFO
        success, deduction_plan = deduct_fifo(
            item_id, quantity, 'reserved', 
            f"Reserved for order {order_id}", 
            created_by=current_user.id if current_user.is_authenticated else None
        )
        
        if not success:
            return False, "Could not reserve inventory using FIFO"
        
        # Update frozen quantity
        item.frozen_quantity += quantity
        
        # Create reservation history entries
        expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        for entry_id, reserve_amount, unit_cost in deduction_plan:
            history = InventoryHistory(
                inventory_item_id=item_id,
                change_type='reserved',
                quantity_change=-reserve_amount,
                unit=item.unit or 'count',
                remaining_quantity=0,  # Reservations don't create new FIFO entries
                fifo_reference_id=entry_id,
                unit_cost=unit_cost,
                note=f"Reserved for order {order_id} (expires {expiration_time})",
                created_by=current_user.id if current_user.is_authenticated else None,
                quantity_used=0.0,  # Reservations don't consume, just hold
                order_id=order_id,
                is_reserved=True,
                expiration_date=expiration_time
            )
            db.session.add(history)
        
        db.session.commit()
        return True, f"Reserved {quantity} {item.unit or 'units'}"
    
    @staticmethod
    def release_reservation(order_id: str) -> Tuple[bool, str]:
        """
        Release a reservation (cart abandoned, order cancelled)
        """
        reservations = InventoryHistory.query.filter(
            and_(
                InventoryHistory.order_id == order_id,
                InventoryHistory.change_type == 'reserved',
                InventoryHistory.is_reserved == True
            )
        ).all()
        
        if not reservations:
            return False, "No reservations found for this order"
        
        total_released = 0
        for reservation in reservations:
            # Credit back to original FIFO entry
            if reservation.fifo_reference_id:
                original_entry = InventoryHistory.query.get(reservation.fifo_reference_id)
                if original_entry:
                    original_entry.remaining_quantity += abs(reservation.quantity_change)
                    
                    # Update frozen quantity
                    item = InventoryItem.query.get(reservation.inventory_item_id)
                    if item:
                        item.frozen_quantity -= abs(reservation.quantity_change)
                        total_released += abs(reservation.quantity_change)
                    
                    # Create release history
                    release_history = InventoryHistory(
                        inventory_item_id=reservation.inventory_item_id,
                        change_type='unreserved',
                        quantity_change=abs(reservation.quantity_change),
                        unit=reservation.unit,
                        remaining_quantity=0,  # Releases don't create new FIFO entries
                        fifo_reference_id=reservation.fifo_reference_id,
                        unit_cost=reservation.unit_cost,
                        note=f"Released reservation for order {order_id}",
                        created_by=current_user.id if current_user.is_authenticated else None,
                        quantity_used=0.0,
                        order_id=order_id
                    )
                    db.session.add(release_history)
            
            # Mark reservation as released
            reservation.is_reserved = False
        
        db.session.commit()
        return True, f"Released {total_released} units from reservation"
    
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
