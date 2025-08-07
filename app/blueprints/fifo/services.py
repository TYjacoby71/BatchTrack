from ...models import InventoryHistory, db, InventoryItem, Batch
from sqlalchemy import and_, desc, or_
from datetime import datetime
from flask_login import current_user
from app.utils.fifo_generator import generate_fifo_code, generate_batch_fifo_code

class FIFOService:
    @staticmethod
    def get_fifo_entries(inventory_item_id):
        """Get all FIFO entries for an item with remaining quantity, excluding expired ones"""
        from app.models.product import ProductSKUHistory

        today = datetime.now().date()

        # Check what type of item this is
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            return []

        if item.type == 'product':
            # For products, ONLY query ProductSKUHistory
            query = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.inventory_item_id == inventory_item_id,
                    ProductSKUHistory.remaining_quantity > 0,
                    # Skip expired entries - they can only be spoiled/trashed
                    db.or_(
                        ProductSKUHistory.expiration_date.is_(None),  # Non-perishable
                        ProductSKUHistory.expiration_date >= today    # Not expired yet
                    )
                )
            )

            # Add organization scoping - always required
            org_id = current_user.organization_id if current_user and current_user.is_authenticated else None
            if org_id:
                query = query.filter(ProductSKUHistory.organization_id == org_id)

            return query.order_by(ProductSKUHistory.timestamp.asc()).all()
        else:
            # For ingredients/containers, query InventoryHistory
            query = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == inventory_item_id,
                    InventoryHistory.remaining_quantity > 0,
                    # Skip expired entries - they can only be spoiled/trashed
                    db.or_(
                        InventoryHistory.expiration_date.is_(None),  # Non-perishable
                        InventoryHistory.expiration_date >= today    # Not expired yet
                    )
                )
            )

            # Add organization scoping - always required
            org_id = current_user.organization_id if current_user and current_user.is_authenticated else None
            if org_id:
                query = query.filter(InventoryHistory.organization_id == org_id)

            return query.order_by(InventoryHistory.timestamp.asc()).all()

    @staticmethod
    def get_expired_fifo_entries(inventory_item_id):
        """Get expired FIFO entries with remaining quantity (for disposal only)"""
        from app.models.product import ProductSKUHistory

        today = datetime.now().date()

        # Check what type of item this is
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            return []

        if item.type == 'product':
            # For products, ONLY query ProductSKUHistory
            query = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.inventory_item_id == inventory_item_id,
                    ProductSKUHistory.remaining_quantity > 0,
                    ProductSKUHistory.expiration_date.isnot(None),
                    ProductSKUHistory.expiration_date < today
                )
            )

            # Add organization scoping - always required
            org_id = current_user.organization_id if current_user and current_user.is_authenticated else None
            if org_id:
                query = query.filter(ProductSKUHistory.organization_id == org_id)

            return query.order_by(ProductSKUHistory.timestamp.asc()).all()
        else:
            # For ingredients/containers, query InventoryHistory
            query = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == inventory_item_id,
                    InventoryHistory.remaining_quantity > 0,
                    InventoryHistory.expiration_date.isnot(None),
                    InventoryHistory.expiration_date < today
                )
            )

            # Add organization scoping - always required
            org_id = current_user.organization_id if current_user and current_user.is_authenticated else None
            if org_id:
                query = query.filter(InventoryHistory.organization_id == org_id)

            return query.order_by(InventoryHistory.timestamp.asc()).all()

    @staticmethod
    def get_all_fifo_entries(inventory_item_id):
        """Get ALL FIFO entries with remaining quantity (including expired) for validation"""
        from app.models.product import ProductSKUHistory

        # Check what type of item this is
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            return []

        if item.type == 'product':
            # For products, ONLY query ProductSKUHistory
            query = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.inventory_item_id == inventory_item_id,
                    ProductSKUHistory.remaining_quantity > 0
                )
            )

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(ProductSKUHistory.organization_id == current_user.organization_id)

            return query.order_by(ProductSKUHistory.timestamp.asc()).all()
        else:
            # For ingredients/containers, query InventoryHistory
            query = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == inventory_item_id,
                    InventoryHistory.remaining_quantity > 0
                )
            )

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(InventoryHistory.organization_id == current_user.organization_id)

            return query.order_by(InventoryHistory.timestamp.asc()).all()



    @staticmethod
    def calculate_deduction_plan(inventory_item_id, quantity, change_type):
        """
        Calculate FIFO deduction plan without executing it
        Returns: (success, deduction_plan, available_quantity)
        """
        # PRODUCTION SAFETY: Only allow expired inventory deduction for disposal operations
        disposal_operations = ['spoil', 'trash', 'expired_disposal', 'expired', 'disposed']

        # For expired disposal, only look at expired lots
        if change_type in disposal_operations:
            expired_entries = FIFOService.get_expired_fifo_entries(inventory_item_id)
            expired_total = sum(entry.remaining_quantity for entry in expired_entries)

            # If we have enough expired stock, use it
            if expired_total >= quantity:
                remaining = quantity
                deduction_plan = []

                for entry in expired_entries:
                    if remaining <= 0:
                        break
                    deduction = min(entry.remaining_quantity, remaining)
                    remaining -= deduction
                    deduction_plan.append((entry.id, deduction, entry.unit_cost))

                return True, deduction_plan, expired_total

        # PRODUCTION SAFETY: For ALL non-disposal operations, ONLY use fresh (non-expired) entries
        # This ensures production batches, sales, reservations, etc. never use expired inventory
        fifo_entries = FIFOService.get_fifo_entries(inventory_item_id)  # Already excludes expired
        available_quantity = sum(entry.remaining_quantity for entry in fifo_entries)

        # Validate no expired entries leaked through
        from datetime import datetime
        today = datetime.now().date()
        for entry in fifo_entries:
            if hasattr(entry, 'expiration_date') and entry.expiration_date and entry.expiration_date < today:
                raise ValueError(f"SAFETY ERROR: Expired entry {entry.id} found in fresh FIFO entries for {change_type}")

        if available_quantity < quantity:
            return False, [], available_quantity

        remaining = quantity
        deduction_plan = []

        for entry in fifo_entries:
            if remaining <= 0:
                break
            deduction = min(entry.remaining_quantity, remaining)
            remaining -= deduction
            deduction_plan.append((entry.id, deduction, entry.unit_cost))

        return True, deduction_plan, available_quantity

    @staticmethod
    def execute_deduction_plan(deduction_plan, inventory_item_id=None):
        """Execute a deduction plan by updating remaining quantities"""
        from app.models.product import ProductSKUHistory

        # Check what type of item this is
        item = InventoryItem.query.get(inventory_item_id) if inventory_item_id else None

        for entry_id, deduct_amount, _ in deduction_plan:
            if item and item.type == 'product':
                # For products, only look in ProductSKUHistory
                entry = ProductSKUHistory.query.get(entry_id)
                if entry:
                    entry.remaining_quantity -= deduct_amount
                    print(f"Updated ProductSKUHistory entry {entry_id}: remaining_quantity now {entry.remaining_quantity}")
                else:
                    print(f"ERROR: Could not find ProductSKUHistory entry {entry_id}")
            else:
                # For raw ingredients/containers, only look in InventoryHistory
                entry = InventoryHistory.query.get(entry_id)
                if entry:
                    entry.remaining_quantity -= deduct_amount
                    print(f"Updated InventoryHistory entry {entry_id}: remaining_quantity now {entry.remaining_quantity}")
                else:
                    print(f"ERROR: Could not find InventoryHistory entry {entry_id}")

        # Commit the changes immediately to ensure they persist
        db.session.commit()

    @staticmethod
    def add_fifo_entry(inventory_item_id, quantity, change_type, unit, notes=None, 
                      cost_per_unit=None, created_by=None, batch_id=None, 
                      expiration_date=None, shelf_life_days=None, order_id=None,
                      source=None, fifo_reference_id=None, **kwargs):
        """
        Add a new FIFO entry for positive inventory changes
        Routes to appropriate history table based on item type
        """
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            raise ValueError("Inventory item not found")

        # Use item unit if none provided, default to 'count' for containers
        if not unit:
            unit = item.unit if item.unit else 'count'

        # Generate FIFO code - for finished_batch, use batch label if available
        if change_type == 'finished_batch' and batch_id:
            batch = db.session.get(Batch, batch_id)
            if batch and batch.label_code:
                fifo_code = f"BCH-{batch.label_code}"
            else:
                fifo_code = generate_fifo_code(change_type, quantity, batch_id)
        else:
            fifo_code = generate_fifo_code(change_type, quantity, batch_id)

        # Check if this is a product item
        if item.type == 'product':
            # Use ProductSKUHistory for products
            from app.models.product import ProductSKUHistory

            history = ProductSKUHistory(
                inventory_item_id=inventory_item_id,
                change_type=change_type,
                quantity_change=quantity,
                unit=unit,
                remaining_quantity=quantity,
                unit_cost=cost_per_unit,
                notes=notes,
                created_by=created_by,
                expiration_date=expiration_date,
                shelf_life_days=shelf_life_days,
                is_perishable=expiration_date is not None,
                batch_id=batch_id if change_type == 'finished_batch' else None,
                fifo_code=fifo_code,
                customer=kwargs.get('customer'),
                sale_price=kwargs.get('sale_price'),
                order_id=order_id,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
            )
        else:
            # Use InventoryHistory for raw ingredients/containers
            history = InventoryHistory(
                inventory_item_id=inventory_item_id,
                change_type=change_type,
                quantity_change=quantity,
                unit=unit,
                remaining_quantity=quantity,
                unit_cost=cost_per_unit,
                note=notes,
                quantity_used=0.0,  # Additions don't consume inventory
                created_by=created_by,
                expiration_date=expiration_date,
                shelf_life_days=shelf_life_days,
                is_perishable=expiration_date is not None,
                batch_id=batch_id if change_type == 'finished_batch' else None,
                used_for_batch_id=batch_id if change_type not in ['restock'] else None,
                fifo_code=fifo_code,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
            )

        db.session.add(history)
        return history



    @staticmethod
    def create_deduction_history(inventory_item_id, deduction_plan, change_type, notes, 
                                batch_id=None, created_by=None, customer=None, sale_price=None, order_id=None):
        """
        Create history entries for deductions using FIFO order
        Routes to correct history table based on item type
        """
        item = InventoryItem.query.get(inventory_item_id)
        history_unit = item.unit if item.unit else 'count'

        history_entries = []

        for entry_id, deduction_amount, unit_cost in deduction_plan:
            used_for_note = "canceled" if change_type == 'refunded' and batch_id else notes
            quantity_used_value = deduction_amount if change_type in ['spoil', 'trash', 'batch', 'use'] else 0.0

            # Generate FIFO code for deduction
            fifo_code = generate_fifo_code(change_type, 0, batch_id)

            # Check if this is a product item
            if item.type == 'product':
                # Use ProductSKUHistory for products
                from app.models.product import ProductSKUHistory

                history = ProductSKUHistory(
                    inventory_item_id=inventory_item_id,
                    change_type=change_type,
                    quantity_change=-deduction_amount,
                    unit=history_unit,
                    remaining_quantity=0.0,  # Deductions ALWAYS have 0 remaining
                    fifo_reference_id=entry_id,
                    unit_cost=unit_cost,
                    notes=f"{used_for_note} (From FIFO #{entry_id})",
                    created_by=created_by,
                    quantity_used=quantity_used_value,
                    batch_id=batch_id,
                    fifo_code=fifo_code,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
                )
            else:
                # Use InventoryHistory for raw ingredients/containers
                history = InventoryHistory(
                    inventory_item_id=inventory_item_id,
                    change_type=change_type,
                    quantity_change=-deduction_amount,
                    unit=history_unit,
                    remaining_quantity=0.0,  # Deductions ALWAYS have 0 remaining
                    fifo_reference_id=entry_id,
                    unit_cost=unit_cost,
                    note=f"{used_for_note} (From FIFO #{entry_id})",
                    created_by=created_by,
                    quantity_used=quantity_used_value,
                    used_for_batch_id=batch_id,
                    fifo_code=fifo_code,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
                )

            db.session.add(history)
            history_entries.append(history)

        return history_entries

    @staticmethod
    def handle_refund_credits(inventory_item_id, quantity, batch_id, notes, created_by, cost_per_unit):
        """
        Handle refund credits by finding original FIFO entries to credit back to
        """
        item = InventoryItem.query.get(inventory_item_id)

        # Find the original deduction entries for this batch
        original_deductions = InventoryHistory.query.filter(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.used_for_batch_id == batch_id,
            InventoryHistory.quantity_change < 0,
            InventoryHistory.fifo_reference_id.isnot(None)
        ).order_by(InventoryHistory.timestamp.desc()).all()

        remaining_to_credit = quantity
        credit_histories = []

        # Credit back to the original FIFO entries
        for deduction in original_deductions:
            if remaining_to_credit <= 0:
                break

            original_fifo_entry = InventoryHistory.query.get(deduction.fifo_reference_id)
            if original_fifo_entry:
                credit_amount = min(remaining_to_credit, abs(deduction.quantity_change))

                # Credit back to the original FIFO entry's remaining quantity
                original_fifo_entry.remaining_quantity += credit_amount
                remaining_to_credit -= credit_amount

                # Create credit history entry
                credit_unit = item.unit if item.unit else 'count'
                credit_history = InventoryHistory(
                    inventory_item_id=inventory_item_id,
                    change_type='refunded',
                    quantity_change=credit_amount,
                    unit=credit_unit,
                    remaining_quantity=0,  # Credits don't create new FIFO entries
                    unit_cost=cost_per_unit,
                    fifo_reference_id=original_fifo_entry.id,
                    note=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                    created_by=created_by,
                    quantity_used=0.0,  # Credits don't consume inventory
                    used_for_batch_id=batch_id,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
                )
                db.session.add(credit_history)
                credit_histories.append(credit_history)

        # If there's still quantity to credit (shouldn't happen in normal cases)
        if remaining_to_credit > 0:
            excess_history = FIFOService.add_fifo_entry(
                inventory_item_id=inventory_item_id,
                quantity=remaining_to_credit,
                change_type='restock',
                unit=item.unit,
                notes=f"{notes} (Excess credit - no original FIFO found)",
                cost_per_unit=cost_per_unit,
                batch_id=batch_id,
                created_by=created_by
            )
            credit_histories.append(excess_history)

        return credit_histories



    @staticmethod
    def recount_fifo(inventory_item_id, new_quantity, note, user_id):
        """
        DEPRECATED: Recount logic moved to centralized inventory adjustment service.
        This function should not be called directly - use process_inventory_adjustment with change_type='recount'
        """
        raise ValueError("Direct FIFO recount calls are deprecated. Use centralized inventory_adjustment service with change_type='recount'")

# Removed deprecated process_adjustment_via_fifo - use inventory_adjustment service
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