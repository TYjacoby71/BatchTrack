
from flask import current_app
from flask_login import current_user
from datetime import datetime, timedelta
from ..models import InventoryItem, InventoryHistory
from ..extensions import db

class InventoryAdjustmentService:
    """Service for handling inventory adjustments with FIFO support"""
    
    @staticmethod
    def adjust_inventory(inventory_item_id, adjustment_amount, reason, notes="", expiration_date=None, cost_per_unit=None):
        """
        Adjust inventory quantity with proper FIFO handling
        
        Args:
            inventory_item_id: ID of the inventory item
            adjustment_amount: Amount to adjust (positive for add, negative for remove)
            reason: Reason for adjustment
            notes: Additional notes
            expiration_date: Expiration date for additions
            cost_per_unit: Cost per unit for additions
        """
        inventory_item = InventoryItem.query.get_or_404(inventory_item_id)
        
        if adjustment_amount > 0:
            return InventoryAdjustmentService._add_inventory(
                inventory_item, adjustment_amount, reason, notes, expiration_date, cost_per_unit
            )
        elif adjustment_amount < 0:
            return InventoryAdjustmentService._remove_inventory(
                inventory_item, abs(adjustment_amount), reason, notes
            )
        else:
            return {"success": False, "message": "Adjustment amount cannot be zero"}

    @staticmethod
    def _add_inventory(inventory_item, amount, reason, notes, expiration_date, cost_per_unit):
        """Add inventory with FIFO entry"""
        try:
            # Create FIFO entry
            fifo_entry = InventoryHistory(
                inventory_item_id=inventory_item.id,
                change_type='addition',
                quantity_change=amount,
                remaining_quantity=amount,
                reason=reason,
                notes=notes,
                expiration_date=expiration_date,
                cost_per_unit=cost_per_unit,
                user_id=current_user.id if current_user.is_authenticated else None,
                timestamp=datetime.utcnow()
            )
            
            # Update main inventory
            inventory_item.quantity += amount
            
            # Update cost tracking if provided
            if cost_per_unit:
                total_cost = amount * cost_per_unit
                if inventory_item.total_cost:
                    inventory_item.total_cost += total_cost
                else:
                    inventory_item.total_cost = total_cost
                
                # Update average cost
                if inventory_item.quantity > 0:
                    inventory_item.average_cost = inventory_item.total_cost / inventory_item.quantity
            
            db.session.add(fifo_entry)
            db.session.commit()
            
            return {
                "success": True,
                "message": f"Added {amount} {inventory_item.unit} to {inventory_item.name}",
                "new_quantity": inventory_item.quantity,
                "fifo_entry_id": fifo_entry.id
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding inventory: {str(e)}")
            return {"success": False, "message": f"Error adding inventory: {str(e)}"}

    @staticmethod
    def _remove_inventory(inventory_item, amount, reason, notes):
        """Remove inventory using FIFO method"""
        try:
            if inventory_item.quantity < amount:
                return {
                    "success": False,
                    "message": f"Insufficient inventory. Available: {inventory_item.quantity}, Requested: {amount}"
                }
            
            remaining_to_remove = amount
            fifo_entries_used = []
            
            # Get FIFO entries (oldest first, with remaining quantity)
            fifo_entries = InventoryHistory.query.filter_by(
                inventory_item_id=inventory_item.id,
                change_type='addition'
            ).filter(
                InventoryHistory.remaining_quantity > 0
            ).order_by(InventoryHistory.timestamp.asc()).all()
            
            # Remove from FIFO entries
            for entry in fifo_entries:
                if remaining_to_remove <= 0:
                    break
                
                if entry.remaining_quantity >= remaining_to_remove:
                    # This entry can fulfill the remaining amount
                    entry.remaining_quantity -= remaining_to_remove
                    fifo_entries_used.append({
                        "entry_id": entry.id,
                        "amount_used": remaining_to_remove,
                        "expiration_date": entry.expiration_date,
                        "original_cost": entry.cost_per_unit
                    })
                    remaining_to_remove = 0
                else:
                    # Use all remaining from this entry
                    amount_used = entry.remaining_quantity
                    fifo_entries_used.append({
                        "entry_id": entry.id,
                        "amount_used": amount_used,
                        "expiration_date": entry.expiration_date,
                        "original_cost": entry.cost_per_unit
                    })
                    remaining_to_remove -= amount_used
                    entry.remaining_quantity = 0
            
            if remaining_to_remove > 0:
                return {
                    "success": False,
                    "message": f"Could not fulfill removal. Missing {remaining_to_remove} units in FIFO."
                }
            
            # Create removal history entry
            removal_entry = InventoryHistory(
                inventory_item_id=inventory_item.id,
                change_type='removal',
                quantity_change=-amount,
                remaining_quantity=0,  # Not applicable for removals
                reason=reason,
                notes=notes,
                user_id=current_user.id if current_user.is_authenticated else None,
                timestamp=datetime.utcnow()
            )
            
            # Update main inventory
            inventory_item.quantity -= amount
            
            # Update cost tracking
            if inventory_item.total_cost and fifo_entries_used:
                cost_removed = sum(
                    entry["amount_used"] * (entry["original_cost"] or 0)
                    for entry in fifo_entries_used
                )
                inventory_item.total_cost = max(0, inventory_item.total_cost - cost_removed)
                
                # Update average cost
                if inventory_item.quantity > 0 and inventory_item.total_cost > 0:
                    inventory_item.average_cost = inventory_item.total_cost / inventory_item.quantity
                else:
                    inventory_item.average_cost = 0
            
            db.session.add(removal_entry)
            db.session.commit()
            
            return {
                "success": True,
                "message": f"Removed {amount} {inventory_item.unit} from {inventory_item.name}",
                "new_quantity": inventory_item.quantity,
                "fifo_entries_used": fifo_entries_used,
                "removal_entry_id": removal_entry.id
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing inventory: {str(e)}")
            return {"success": False, "message": f"Error removing inventory: {str(e)}"}

    @staticmethod
    def get_fifo_summary(inventory_item_id):
        """Get FIFO summary for an inventory item"""
        try:
            entries = InventoryHistory.query.filter_by(
                inventory_item_id=inventory_item_id,
                change_type='addition'
            ).filter(
                InventoryHistory.remaining_quantity > 0
            ).order_by(InventoryHistory.timestamp.asc()).all()
            
            summary = []
            for entry in entries:
                summary.append({
                    "id": entry.id,
                    "date_added": entry.timestamp,
                    "expiration_date": entry.expiration_date,
                    "remaining_quantity": entry.remaining_quantity,
                    "original_quantity": entry.quantity_change,
                    "cost_per_unit": entry.cost_per_unit,
                    "notes": entry.notes
                })
            
            return summary
            
        except Exception as e:
            current_app.logger.error(f"Error getting FIFO summary: {str(e)}")
            return []

    @staticmethod
    def check_expiring_inventory(days_ahead=7):
        """Check for inventory items expiring within specified days"""
        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            expiring_entries = InventoryHistory.query.filter(
                InventoryHistory.change_type == 'addition',
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date <= cutoff_date,
                InventoryHistory.expiration_date.isnot(None)
            ).order_by(InventoryHistory.expiration_date.asc()).all()
            
            expiring_items = []
            for entry in expiring_entries:
                inventory_item = InventoryItem.query.get(entry.inventory_item_id)
                if inventory_item:
                    expiring_items.append({
                        "inventory_item": inventory_item,
                        "fifo_entry": entry,
                        "days_until_expiration": (entry.expiration_date.date() - datetime.utcnow().date()).days
                    })
            
            return expiring_items
            
        except Exception as e:
            current_app.logger.error(f"Error checking expiring inventory: {str(e)}")
            return []

    @staticmethod
    def get_adjustment_history(inventory_item_id, limit=50):
        """Get adjustment history for an inventory item"""
        try:
            history = InventoryHistory.query.filter_by(
                inventory_item_id=inventory_item_id
            ).order_by(InventoryHistory.timestamp.desc()).limit(limit).all()
            
            return history
            
        except Exception as e:
            current_app.logger.error(f"Error getting adjustment history: {str(e)}")
            return []

    @staticmethod
    def validate_adjustment(inventory_item_id, adjustment_amount):
        """Validate if an adjustment is possible"""
        try:
            inventory_item = InventoryItem.query.get(inventory_item_id)
            if not inventory_item:
                return {"valid": False, "message": "Inventory item not found"}
            
            if adjustment_amount < 0 and inventory_item.quantity < abs(adjustment_amount):
                return {
                    "valid": False,
                    "message": f"Insufficient inventory. Available: {inventory_item.quantity}, Requested: {abs(adjustment_amount)}"
                }
            
            return {"valid": True, "message": "Adjustment is valid"}
            
        except Exception as e:
            return {"valid": False, "message": f"Validation error: {str(e)}"}
