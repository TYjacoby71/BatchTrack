from ...models import InventoryHistory, db, InventoryItem
from sqlalchemy import and_, desc, or_
from datetime import datetime
from flask_login import current_user
from app.utils.fifo_generator import generate_fifo_id
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from flask_login import current_user
from sqlalchemy import func, and_

from ...models import db, InventoryItem, InventoryHistory

class FIFOService:
    """Centralized FIFO service for inventory management"""

    @staticmethod
    def get_all_fifo_entries(inventory_item_id: int):
        """Get all FIFO entries with remaining quantity > 0"""
        return InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).order_by(InventoryHistory.timestamp.asc()).all()

    @staticmethod
    def get_fresh_fifo_entries(inventory_item_id: int):
        """Get non-expired FIFO entries with remaining quantity > 0"""
        today = datetime.now().date()
        return InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                db.or_(
                    InventoryHistory.expiration_date.is_(None),  # Non-perishable
                    InventoryHistory.expiration_date >= today    # Not expired yet
                )
            )
        ).order_by(InventoryHistory.timestamp.asc()).all()

    @staticmethod
    def get_expired_fifo_entries(inventory_item_id: int):
        """Get expired FIFO entries with remaining quantity > 0 (frozen)"""
        today = datetime.now().date()
        return InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date.isnot(None),
                InventoryHistory.expiration_date < today
            )
        ).order_by(InventoryHistory.timestamp.asc()).all()

    @staticmethod
    def calculate_deduction_plan(inventory_item_id: int, quantity_needed: float, change_type: str):
        """
        Calculate how to deduct quantity using FIFO order
        Returns: (success, deduction_plan, available_qty)
        """
        # For expired disposal, prioritize expired entries
        if change_type in ['spoil', 'trash', 'expired_disposal']:
            expired_entries = FIFOService.get_expired_fifo_entries(inventory_item_id)
            expired_total = sum(entry.remaining_quantity for entry in expired_entries)

            if expired_total >= quantity_needed:
                # Use only expired entries
                deduction_plan = []
                remaining_needed = quantity_needed

                for entry in expired_entries:
                    if remaining_needed <= 0:
                        break

                    deduction_amount = min(entry.remaining_quantity, remaining_needed)
                    deduction_plan.append((entry.id, deduction_amount, entry.unit_cost))
                    remaining_needed -= deduction_amount

                return True, deduction_plan, expired_total

        # Regular FIFO deduction from fresh entries
        fresh_entries = FIFOService.get_fresh_fifo_entries(inventory_item_id)
        fresh_total = sum(entry.remaining_quantity for entry in fresh_entries)

        if fresh_total < quantity_needed:
            return False, [], fresh_total

        deduction_plan = []
        remaining_needed = quantity_needed

        for entry in fresh_entries:
            if remaining_needed <= 0:
                break

            deduction_amount = min(entry.remaining_quantity, remaining_needed)
            deduction_plan.append((entry.id, deduction_amount, entry.unit_cost))
            remaining_needed -= deduction_amount

        return True, deduction_plan, fresh_total

    @staticmethod
    def execute_deduction_plan(deduction_plan: List[Tuple[int, float, float]]):
        """Execute the deduction plan by updating remaining quantities"""
        for entry_id, deduction_amount, _ in deduction_plan:
            entry = InventoryHistory.query.get(entry_id)
            if entry:
                entry.remaining_quantity -= deduction_amount

    @staticmethod
    def add_fifo_entry(inventory_item_id: int, quantity: float, change_type: str, 
                      unit: str, notes: str, cost_per_unit: float = None,
                      expiration_date: datetime = None, shelf_life_days: int = None,
                      batch_id: int = None, created_by: int = None):
        """Add new FIFO entry for positive inventory changes"""

        history = InventoryHistory(
            inventory_item_id=inventory_item_id,
            change_type=change_type,
            quantity_change=quantity,
            unit=unit,
            remaining_quantity=quantity if change_type in ['restock', 'finished_batch', 'manual_addition'] else None,
            unit_cost=cost_per_unit,
            note=notes,
            expiration_date=expiration_date,
            shelf_life_days=shelf_life_days,
            is_perishable=expiration_date is not None,
            batch_id=batch_id if change_type == 'finished_batch' else None,
            created_by=created_by,
            organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
        )

        db.session.add(history)

    @staticmethod
    def create_deduction_history(inventory_item_id: int, deduction_plan: List[Tuple[int, float, float]], 
                                change_type: str, notes: str, batch_id: int = None, 
                                created_by: int = None, customer: str = None, 
                                sale_price: float = None, order_id: str = None):
        """Create history entries for deductions"""

        for entry_id, deduction_amount, unit_cost in deduction_plan:
            # Get the unit from the original entry
            original_entry = InventoryHistory.query.get(entry_id)
            unit = original_entry.unit if original_entry else 'count'

            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type=change_type,
                quantity_change=-deduction_amount,  # Negative for deductions
                unit=unit,
                remaining_quantity=0,  # Deductions don't create new FIFO entries
                fifo_reference_id=entry_id,
                unit_cost=unit_cost,
                note=f"{notes} (From FIFO #{entry_id})",
                batch_id=batch_id,
                created_by=created_by,
                quantity_used=deduction_amount if change_type in ['spoil', 'trash', 'batch', 'use'] else 0.0,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
            )

            db.session.add(history)

    @staticmethod
    def handle_refund_credits(inventory_item_id: int, quantity: float, batch_id: int, 
                             notes: str, created_by: int, cost_per_unit: float):
        """Handle refund credits by adding back to newest FIFO entry or creating new one"""

        # Try to find the most recent entry from the same batch
        recent_entry = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.batch_id == batch_id,
                InventoryHistory.remaining_quantity.isnot(None)
            )
        ).order_by(InventoryHistory.timestamp.desc()).first()

        if recent_entry:
            # Add back to existing entry
            recent_entry.remaining_quantity += quantity

            # Create history record
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type='refunded',
                quantity_change=quantity,
                unit=recent_entry.unit,
                remaining_quantity=0,  # This is just a record, not a new FIFO entry
                fifo_reference_id=recent_entry.id,
                unit_cost=cost_per_unit,
                note=f"{notes} (Credited to FIFO #{recent_entry.id})",
                batch_id=batch_id,
                created_by=created_by,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
            )
            db.session.add(history)
        else:
            # Create new FIFO entry
            FIFOService.add_fifo_entry(
                inventory_item_id=inventory_item_id,
                quantity=quantity,
                change_type='refunded',
                unit='count',  # Default unit
                notes=notes,
                cost_per_unit=cost_per_unit,
                batch_id=batch_id,
                created_by=created_by
            )

    

    

    @staticmethod
    def deduct_fifo(inventory_item_id, quantity, change_type=None, notes=None, batch_id=None, created_by=None):
        """Legacy function - use FIFOService.calculate_deduction_plan and execute_deduction_plan instead"""
        success, deduction_plan, _ = FIFOService.calculate_deduction_plan(inventory_item_id, quantity, change_type)
        if success:
            FIFOService.execute_deduction_plan(deduction_plan)
        return success, deduction_plan

# Legacy function aliases for backward compatibility
def get_fifo_entries(inventory_item_id):
    return FIFOService.get_fifo_entries(inventory_item_id)

def get_expired_fifo_entries(inventory_item_id):
    return FIFOService.get_expired_fifo_entries(inventory_item_id)

def deduct_fifo(inventory_item_id, quantity, change_type=None, notes=None, batch_id=None, created_by=None):
    """Legacy function - use FIFOService.calculate_deduction_plan and execute_deduction_plan instead"""
    success, deduction_plan, _ = FIFOService.calculate_deduction_plan(inventory_item_id, quantity, change_type)
    if success:
        FIFOService.execute_deduction_plan(deduction_plan)
    return success, deduction_plan

def recount_fifo(inventory_item_id, new_quantity, note, user_id):
    return FIFOService.recount_fifo(inventory_item_id, new_quantity, note, user_id)

def update_fifo_perishable_status(inventory_item_id, shelf_life_days):
    """Updates perishable status for all FIFO entries with remaining quantity"""
    from ...blueprints.expiration.services import ExpirationService
    ExpirationService.update_fifo_expiration_data(inventory_item_id, shelf_life_days)