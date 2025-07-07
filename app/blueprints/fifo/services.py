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

    # PRODUCT SKU FIFO METHODS
    @staticmethod
    def get_product_sku_fifo_entries(sku_id: int, include_expired: bool = False):
        """Get ProductSKU FIFO entries with remaining quantity > 0"""
        from ...models.product import ProductSKUHistory

        query = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.sku_id == sku_id,
                ProductSKUHistory.remaining_quantity > 0
            )
        )

        if not include_expired:
            today = datetime.now().date()
            query = query.filter(
                db.or_(
                    ProductSKUHistory.expiration_date.is_(None),  # Non-perishable
                    ProductSKUHistory.expiration_date >= today    # Not expired yet
                )
            )

        return query.order_by(ProductSKUHistory.timestamp.asc()).all()

    @staticmethod
    def calculate_product_sku_deduction_plan(sku_id: int, quantity_needed: float, change_type: str):
        """Calculate deduction plan for ProductSKU using FIFO"""
        from ...models.product import ProductSKUHistory

        # For expired disposal, prioritize expired entries
        if change_type in ['spoil', 'trash', 'expired_disposal']:
            today = datetime.now().date()
            expired_entries = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.sku_id == sku_id,
                    ProductSKUHistory.remaining_quantity > 0,
                    ProductSKUHistory.expiration_date.isnot(None),
                    ProductSKUHistory.expiration_date < today
                )
            ).order_by(ProductSKUHistory.timestamp.asc()).all()

            expired_total = sum(entry.remaining_quantity for entry in expired_entries)

            if expired_total >= quantity_needed:
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
        fresh_entries = FIFOService.get_product_sku_fifo_entries(sku_id, include_expired=False)
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
    def execute_product_sku_deduction_plan(deduction_plan: List[Tuple[int, float, float]]):
        """Execute deduction plan for ProductSKU"""
        from ...models.product import ProductSKUHistory

        for entry_id, deduction_amount, _ in deduction_plan:
            entry = ProductSKUHistory.query.get(entry_id)
            if entry:
                entry.remaining_quantity -= deduction_amount

    @staticmethod
    def add_product_sku_fifo_entry(sku_id: int, quantity: float, change_type: str,
                                     unit: str, notes: str, cost_per_unit: float = None,
                                     expiration_date: datetime = None, shelf_life_days: int = None,
                                     batch_id: int = None, created_by: int = None):
        """Add new FIFO entry for positive ProductSKU changes"""
        from ...models.product import ProductSKUHistory, ProductSKU

        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("Product SKU not found")

        history = ProductSKUHistory(
            sku_id=sku_id,
            change_type=change_type,
            quantity_change=quantity,
            unit=unit,
            remaining_quantity=quantity,
            unit_cost=cost_per_unit,
            note=notes,
            expiration_date=expiration_date,
            shelf_life_days=shelf_life_days,
            is_perishable=expiration_date is not None,
            batch_id=batch_id if change_type == 'finished_batch' else None,
            created_by=created_by,
            organization_id=current_user.organization_id if current_user and current_user.is_authenticated else sku.organization_id
        )

        db.session.add(history)
        return history

    @staticmethod
    def create_product_sku_deduction_history(sku_id: int, deduction_plan: List[Tuple[int, float, float]],
                                               change_type: str, notes: str, batch_id: int = None,
                                               created_by: int = None, customer: str = None,
                                               sale_price: float = None, order_id: str = None):
        """Create history entries for ProductSKU deductions"""
        from ...models.product import ProductSKUHistory, ProductSKU

        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("Product SKU not found")

        history_entries = []

        for entry_id, deduction_amount, unit_cost in deduction_plan:
            # Get the original entry
            original_entry = ProductSKUHistory.query.get(entry_id)
            if not original_entry:
                 raise ValueError(f"Original entry with ID {entry_id} not found")

            history = ProductSKUHistory(
                sku_id=sku_id,
                change_type=change_type,
                quantity_change=-deduction_amount,  # Negative for deductions
                unit=original_entry.unit if original_entry else 'count',
                remaining_quantity=0,
                fifo_reference_id=entry_id,
                unit_cost=unit_cost,
                note=f"{notes} (From FIFO #{entry_id})",
                batch_id=batch_id,
                created_by=created_by,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else sku.organization_id
            )

            db.session.add(history)
            history_entries.append(history)

        return history_entries

    @staticmethod
    def handle_product_sku_refund_credits(sku_id: int, quantity: float, batch_id: int,
                                            notes: str, created_by: int, cost_per_unit: float):
        """Handle refund credits for product SKUs by finding original FIFO entries to credit back to"""
        from ...models.product import ProductSKUHistory, ProductSKU

        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("Product SKU not found")

        # Find the original deduction entries for this batch
        original_deductions = ProductSKUHistory.query.filter(
            ProductSKUHistory.sku_id == sku_id,
            ProductSKUHistory.batch_id == batch_id,
            ProductSKUHistory.quantity_change < 0,
            ProductSKUHistory.fifo_reference_id.isnot(None)
        ).order_by(ProductSKUHistory.timestamp.desc()).all()

        remaining_to_credit = quantity
        credit_histories = []

        # Credit back to the original FIFO entries
        for deduction in original_deductions:
            if remaining_to_credit <= 0:
                break

            original_fifo_entry = ProductSKUHistory.query.get(deduction.fifo_reference_id)
            if original_fifo_entry:
                credit_amount = min(remaining_to_credit, abs(deduction.quantity_change))

                # Credit back to the original FIFO entry's remaining quantity
                original_fifo_entry.remaining_quantity += credit_amount
                remaining_to_credit -= credit_amount

                # Create credit history entry
                credit_history = ProductSKUHistory(
                    sku_id=sku_id,
                    change_type='refunded',
                    quantity_change=credit_amount,
                    unit=original_fifo_entry.unit,
                    remaining_quantity=0,  # Credits don't create new FIFO entries
                    unit_cost=cost_per_unit,
                    fifo_reference_id=original_fifo_entry.id,
                    note=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                    batch_id=batch_id,
                    created_by=created_by,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else sku.organization_id
                )
                db.session.add(credit_history)
                credit_histories.append(credit_history)

        # If there's still quantity to credit (shouldn't happen in normal cases)
        if remaining_to_credit > 0:
             # Assuming the function add_product_sku_fifo_entry exists
            excess_history = FIFOService.add_product_sku_fifo_entry(
                sku_id=sku_id,
                quantity=remaining_to_credit,
                change_type='restock',
                unit='count',  # Assuming a default unit
                notes=f"{notes} (Excess credit - no original FIFO found)",
                cost_per_unit=cost_per_unit,
                batch_id=batch_id,
                created_by=created_by
            )
            credit_histories.append(excess_history)

        return credit_histories

    @staticmethod
    def recount_product_sku_fifo(sku_id: int, new_quantity: float, note: str, user_id: int):
        """
        Handles recounts for product SKUs with proper FIFO integrity
        """
        from ...models.product import ProductSKUHistory, ProductSKU

        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("Product SKU not found")

        current_entries = FIFOService.get_product_sku_fifo_entries(sku_id)
        current_total = sum(entry.remaining_quantity for entry in current_entries)

        difference = new_quantity - current_total

        if difference == 0:
            return True

        # Use same unit logic as inventory_adjustment service
        history_unit = 'count'

        # Handle reduction in quantity
        if difference < 0:
            success, deduction_plan, _ = FIFOService.calculate_product_sku_deduction_plan(
                sku_id, abs(difference), 'recount'
            )

            if not success:
                return False

            # Execute the deduction
            FIFOService.execute_product_sku_deduction_plan(deduction_plan)

            # Create history entries
            FIFOService.create_product_sku_deduction_history(
                sku_id, deduction_plan, 'recount', note,
                created_by=user_id
            )

        # Handle increase in quantity
        else:
             # Get only restock entries that aren't at capacity
            unfilled_entries = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.sku_id == sku_id,
                    ProductSKUHistory.remaining_quantity < ProductSKUHistory.quantity_change,
                    ProductSKUHistory.change_type == 'restock'
                )
            ).order_by(ProductSKUHistory.timestamp.desc()).all()

            remaining_to_add = difference

            # First try to fill existing FIFO entries
            for entry in unfilled_entries:
                if remaining_to_add <= 0:
                    break

                available_capacity = entry.quantity_change - entry.remaining_quantity
                fill_amount = min(available_capacity, remaining_to_add)

                if fill_amount > 0:
                    # Log the recount but don't create new FIFO entry
                    history = ProductSKUHistory(
                        sku_id=sku_id,
                        change_type='recount',
                        quantity_change=fill_amount,
                        unit=history_unit,
                        remaining_quantity=0,  # Not a FIFO entry
                        fifo_reference_id=entry.id,
                        note=f"Recount restored to FIFO entry #{entry.id}",
                        created_by=user_id,
                        organization_id=current_user.organization_id if current_user and current_user.is_authenticated else sku.organization_id
                    )
                    db.session.add(history)

                    # Update the original FIFO entry
                    entry.remaining_quantity += fill_amount
                    remaining_to_add -= fill_amount

            # Only create new FIFO entry if we couldn't fill existing ones
            if remaining_to_add > 0:
                FIFOService.add_product_sku_fifo_entry(
                    sku_id=sku_id,
                    quantity=remaining_to_add,
                    change_type='restock',
                    unit=history_unit,
                    notes=f"New stock from recount after filling existing FIFO entries",
                    created_by=user_id
                )

        db.session.commit()
        return True

    # Product SKU methods End

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