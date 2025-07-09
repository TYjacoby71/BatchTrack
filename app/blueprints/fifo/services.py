from ...models import InventoryHistory, db, InventoryItem
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

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(ProductSKUHistory.organization_id == current_user.organization_id)

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

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(InventoryHistory.organization_id == current_user.organization_id)

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

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(ProductSKUHistory.organization_id == current_user.organization_id)

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

            # Add organization scoping if user is authenticated
            if current_user and current_user.is_authenticated:
                query = query.filter(InventoryHistory.organization_id == current_user.organization_id)

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
        # For expired disposal, only look at expired lots
        if change_type in ['spoil', 'trash', 'expired_disposal']:
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

        # Regular FIFO (non-expired entries)
        fifo_entries = FIFOService.get_fifo_entries(inventory_item_id)
        available_quantity = sum(entry.remaining_quantity for entry in fifo_entries)

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

        # Generate FIFO code
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
    def create_reservation_tracking(inventory_item_id, deduction_plan, order_id, notes, 
                                   created_by=None, customer=None, sale_price=None):
        """
        Create reservation entries with FIFO lot tracking
        """
        from app.models.reservation import Reservation
        from app.services.reservation_service import ReservationService

        # Get the product item and reserved item
        product_item = InventoryItem.query.get(inventory_item_id)
        if not product_item or product_item.type != 'product':
            return False

        reserved_item = ReservationService.get_reserved_item_for_product(inventory_item_id)
        if not reserved_item:
            return False

        # Create reservation entries for each FIFO lot
        for fifo_entry_id, qty_deducted, cost_per_unit in deduction_plan:
            reservation = Reservation(
                order_id=order_id,
                product_item_id=inventory_item_id,
                reserved_item_id=reserved_item.id,
                quantity=qty_deducted,
                unit=product_item.unit,
                unit_cost=cost_per_unit,
                sale_price=sale_price,
                source_fifo_id=fifo_entry_id,
                status='active',
                notes=notes,
                created_by=created_by,
                organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
            )
            db.session.add(reservation)

        return True

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
        Handles recounts with proper FIFO integrity and expiration tracking
        """
        from app.models.product import ProductSKUHistory

        item = InventoryItem.query.get(inventory_item_id)
        current_entries = FIFOService.get_fifo_entries(inventory_item_id)
        current_total = sum(entry.remaining_quantity for entry in current_entries)

        difference = new_quantity - current_total

        if difference == 0:
            return True

        # Use same unit logic as inventory_adjustment service
        history_unit = 'count' if item.type == 'container' else item.unit

        # Handle reduction in quantity
        if difference < 0:
            success, deduction_plan, _ = FIFOService.calculate_deduction_plan(
                inventory_item_id, abs(difference), 'recount'
            )

            if not success:
                return False

            # Execute the deduction (only update remaining quantities)
            FIFOService.execute_deduction_plan(deduction_plan, inventory_item_id)

            # For products, don't create individual deduction entries during recount
            # The calling code will create a single recount summary entry
            if item.type != 'product':
                # Only create deduction history entries for raw inventory
                FIFOService.create_deduction_history(
                    inventory_item_id, deduction_plan, 'recount', note, 
                    created_by=user_id
                )

        # Handle increase in quantity    
        else:
            # Handle product vs raw inventory differently
            if item.type == 'product':
                # For products, look in ProductSKUHistory for entries with available capacity
                # This includes both positive additions (restocks) and negative deductions (sales) that have remaining space
                unfilled_entries = ProductSKUHistory.query.filter(
                    and_(
                        ProductSKUHistory.inventory_item_id == inventory_item_id,
                        ProductSKUHistory.remaining_quantity > 0,  # Has available capacity
                        db.or_(
                            # Positive entries that aren't fully filled
                            and_(
                                ProductSKUHistory.quantity_change > 0,
                                ProductSKUHistory.remaining_quantity < ProductSKUHistory.quantity_change
                            ),
                            # Negative entries (sales/gifts) that have refund capacity
                            and_(
                                ProductSKUHistory.quantity_change < 0,
                                ProductSKUHistory.remaining_quantity > 0
                            )
                        )
                    )
                ).order_by(ProductSKUHistory.timestamp.asc()).all()  # Fill oldest first (FIFO order)
            else:
                # For raw inventory, look in InventoryHistory for entries with available capacity
                unfilled_entries = InventoryHistory.query.filter(
                    and_(
                        InventoryHistory.inventory_item_id == inventory_item_id,
                        InventoryHistory.remaining_quantity > 0,  # Has available capacity
                        db.or_(
                            # Positive entries that aren't fully filled
                            and_(
                                InventoryHistory.quantity_change > 0,
                                InventoryHistory.remaining_quantity < InventoryHistory.quantity_change
                            ),
                            # Negative entries (sales/usage) that have refund capacity
                            and_(
                                InventoryHistory.quantity_change < 0,
                                InventoryHistory.remaining_quantity > 0
                            )
                        )
                    )
                ).order_by(InventoryHistory.timestamp.asc()).all()  # Fill oldest first (FIFO order)

            remaining_to_add = difference

            # First try to fill existing FIFO entries
            for entry in unfilled_entries:
                if remaining_to_add <= 0:
                    break

                available_capacity = entry.quantity_change - entry.remaining_quantity
                fill_amount = min(available_capacity, remaining_to_add)

                if fill_amount > 0:
                    # Update the original FIFO entry
                    entry.remaining_quantity += fill_amount
                    remaining_to_add -= fill_amount

                    # For products, don't create individual restoration entries during recount
                    # The calling code will create a single recount summary entry
                    if item.type != 'product':
                        # Only log restoration for raw inventory
                        history = InventoryHistory(
                            inventory_item_id=inventory_item_id,
                            change_type='recount',
                            quantity_change=fill_amount,
                            unit=history_unit,
                            remaining_quantity=0,  # Not a FIFO entry
                            fifo_reference_id=entry.id,
                            note=f"Recount restored to FIFO entry #{entry.id}",
                            created_by=user_id,
                            quantity_used=0.0,
                            organization_id=current_user.organization_id if current_user else item.organization_id
                        )
                        db.session.add(history)

            # Only create new FIFO entry if we couldn't fill existing ones
            if remaining_to_add > 0:
                # For all items, create new FIFO entry with proper recount change_type
                # This ensures consistent FIFO code generation
                FIFOService.add_fifo_entry(
                    inventory_item_id=inventory_item_id,
                    quantity=remaining_to_add,
                    change_type='recount',  # Use 'recount' to generate LOT prefix for positive additions
                    unit=history_unit,
                    notes=f"New stock from recount",
                    created_by=user_id
                )

        db.session.commit()
        return True

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