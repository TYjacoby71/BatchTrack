from datetime import datetime
from typing import Optional, List, Dict
from flask_login import current_user
from sqlalchemy import func, desc, asc

from ..models import db, ProductSKU, ProductSKUHistory
from ..utils.fifo_generator import generate_fifo_code as generate_fifo_id

class ProductInventoryService:
    """Product inventory service - mirrors raw inventory system with SKU+History only"""

    @staticmethod
    def add_stock(sku_id: int, quantity: float, unit_cost: float = 0, 
                  batch_id: Optional[int] = None, container_id: Optional[int] = None,
                  notes: str = '', change_type: str = 'manual_addition',
                  sale_price: Optional[float] = None, customer: Optional[str] = None,
                  sale_location: str = 'manual') -> ProductSKUHistory:
        """Add stock to SKU - creates FIFO history entry like InventoryHistory"""

        sku = ProductSKU.query.get_or_404(sku_id)
        old_quantity = sku.current_quantity
        new_quantity = old_quantity + quantity

        # Calculate weighted average cost for new additions
        if change_type in ['batch_addition', 'manual_addition', 'restock'] and quantity > 0:
            if old_quantity > 0 and sku.unit_cost:
                current_value = old_quantity * sku.unit_cost
                new_value = quantity * unit_cost
                weighted_avg_cost = (current_value + new_value) / (old_quantity + quantity)
                sku.unit_cost = weighted_avg_cost
            elif unit_cost > 0:
                sku.unit_cost = unit_cost

        # Update SKU current quantity
        sku.current_quantity = new_quantity
        sku.last_updated = datetime.utcnow()

        # Determine FIFO source (batch label or generated fifo code)
        fifo_source = None
        if batch_id and change_type == 'batch_addition':
            from ..models import Batch
            batch = Batch.query.get(batch_id)
            fifo_source = batch.label_code if batch else generate_fifo_id(f"SKU{sku_id}")
        else:
            fifo_source = generate_fifo_id(f"SKU{sku_id}")

        # Ensure notes is a string (handle case where dict is passed)
        notes_str = notes
        if isinstance(notes, dict):
            # Convert dict to string representation
            notes_str = f"User notes: {notes.get('user_notes', '')}, Sale price: {notes.get('sale_price', 0.0)}, Customer: {notes.get('customer', '')}, Unit cost: {notes.get('unit_cost', 0.0)}"
        elif not isinstance(notes, str):
            notes_str = str(notes)

        # Create FIFO history entry (like InventoryHistory with remaining_quantity)
        history = ProductSKUHistory(
            sku_id=sku_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,
            quantity_change=quantity,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            remaining_quantity=quantity if change_type in ['batch_addition', 'manual_addition', 'restock', 'overflow_restock'] else 0,
            original_quantity=quantity,
            unit=sku.unit,
            unit_cost=unit_cost or sku.unit_cost,
            sale_price=sale_price,
            customer=customer,
            batch_id=batch_id,
            container_id=container_id,
            fifo_code=generate_fifo_id('refunded'),
            fifo_source=fifo_source,
            notes=notes_str,
            note=notes_str,  # Mirror field
            created_by=current_user.id if current_user.is_authenticated else None,
            quantity_used=0.0,  # Additions don't consume
            sale_location=sale_location,
            organization_id=current_user.organization_id if current_user.is_authenticated else 1  # Default to org 1 if no user
        )

        db.session.add(history)
        return history

    @staticmethod
    def deduct_stock(sku_id: int, quantity: float, change_type: str = 'manual_deduction',
                     notes: str = '', sale_price: Optional[float] = None,
                     customer: Optional[str] = None, sale_location: str = 'manual',
                     order_id: Optional[str] = None, used_for_batch_id: Optional[int] = None) -> bool:
        """Deduct stock using FIFO - mirrors raw inventory deduct_fifo"""

        sku = ProductSKU.query.get_or_404(sku_id)

        if sku.current_quantity < quantity:
            return False  # Insufficient stock

        # Get FIFO entries with remaining quantity (like InventoryHistory)
        fifo_entries = ProductSKUHistory.query.filter_by(sku_id=sku_id)\
            .filter(ProductSKUHistory.remaining_quantity > 0)\
            .order_by(ProductSKUHistory.timestamp.asc()).all()

        # Check if enough stock available
        total_available = sum(entry.remaining_quantity for entry in fifo_entries)
        if total_available < quantity:
            return False

        remaining_to_deduct = quantity
        old_quantity = sku.current_quantity

        # Execute FIFO deductions
        for entry in fifo_entries:
            if remaining_to_deduct <= 0:
                break

            deduct_amount = min(entry.remaining_quantity, remaining_to_deduct)
            entry.remaining_quantity -= deduct_amount
            remaining_to_deduct -= deduct_amount

            # Ensure notes is a string (handle case where dict is passed)
            notes_str = notes
            if isinstance(notes, dict):
                # Convert dict to string representation
                notes_str = f"User notes: {notes.get('user_notes', '')}, Sale price: {notes.get('sale_price', 0.0)}, Customer: {notes.get('customer', '')}, Unit cost: {notes.get('unit_cost', 0.0)}"
            elif not isinstance(notes, str):
                notes_str = str(notes)

            # Track quantities before this deduction for history
            old_qty_for_history = sku.current_quantity
            sku.current_quantity -= deduct_amount  # Update SKU quantity
            
            # Create individual deduction history for each FIFO entry used
            deduction_history = ProductSKUHistory(
                sku_id=sku_id,
                timestamp=datetime.utcnow(),
                change_type=change_type,
                quantity_change=-deduct_amount,
                old_quantity=old_qty_for_history,
                new_quantity=sku.current_quantity,
                remaining_quantity=0,  # Deductions don't have remaining
                unit=sku.unit,
                unit_cost=entry.unit_cost,  # Use cost from original FIFO entry
                sale_price=sale_price,
                customer=customer,
                fifo_code=generate_fifo_id('refunded'),
                fifo_reference_id=entry.id,  # Reference to source FIFO entry
                fifo_source=entry.fifo_source,  # Use source from original FIFO entry
                notes=f"{notes_str} (From FIFO #{entry.id})",
                note=f"{notes_str} (From FIFO #{entry.id})",
                created_by=current_user.id if current_user.is_authenticated else None,
                quantity_used=deduct_amount if change_type in ['spoil', 'trash', 'damage', 'sale'] else 0.0,
                sale_location=sale_location,
                order_id=order_id,
                organization_id=current_user.organization_id if current_user.is_authenticated else 1  # Default to org 1 if no user
            )
            db.session.add(deduction_history)

        # Update timestamp (quantity already updated in loop)
        sku.last_updated = datetime.utcnow()

        return True

    @staticmethod
    def recount_sku(sku_id: int, new_quantity: float, notes: str = '') -> bool:
        """Recount SKU inventory - mirrors raw inventory recount"""

        sku = ProductSKU.query.get_or_404(sku_id)
        old_quantity = sku.current_quantity
        difference = new_quantity - old_quantity

        if difference == 0:
            return True

        if difference < 0:
            # Reduce stock using FIFO
            return ProductInventoryService.deduct_stock(
                sku_id=sku_id,
                quantity=abs(difference),
                change_type='recount',
                notes=f"Recount adjustment: {old_quantity} → {new_quantity}. {notes}"
            )
        else:
            # Add stock
            ProductInventoryService.add_stock(
                sku_id=sku_id,
                quantity=difference,
                unit_cost=sku.unit_cost or 0,
                change_type='recount',
                notes=f"Recount adjustment: {old_quantity} → {new_quantity}. {notes}"
            )
            return True

    @staticmethod
    def adjust_fifo_entry(history_id: int, quantity: float, change_type: str,
                         notes: str = '') -> bool:
        """Adjust specific FIFO entry - like adjusting InventoryHistory"""

        history_entry = ProductSKUHistory.query.get_or_404(history_id)
        sku = ProductSKU.query.get_or_404(history_entry.sku_id)

        original_remaining = history_entry.remaining_quantity

        if change_type == 'recount':
            # Set new remaining for this entry
            quantity_change = quantity - original_remaining
            history_entry.remaining_quantity = max(0, quantity)
        else:
            # Deduction from this specific entry
            if quantity > original_remaining:
                return False  # Can't deduct more than available
            quantity_change = -quantity
            history_entry.remaining_quantity = max(0, original_remaining - quantity)

        # Update SKU total
        sku.current_quantity += quantity_change
        sku.last_updated = datetime.utcnow()

        # Create adjustment history entry
        adjustment_history = ProductSKUHistory(
            sku_id=history_entry.sku_id,
            timestamp=datetime.utcnow(),
            change_type=f'fifo_{change_type}',
            quantity_change=quantity_change,
            old_quantity=sku.current_quantity - quantity_change,
            new_quantity=sku.current_quantity,
            remaining_quantity=0,
            unit=sku.unit,
            unit_cost=history_entry.unit_cost,  # Use cost from original entry
            fifo_code=generate_fifo_id('refunded'),
            fifo_reference_id=history_entry.id,
            notes=f"FIFO entry #{history_id} adjustment: {original_remaining} → {history_entry.remaining_quantity}. {notes}",
            note=f"FIFO entry #{history_id} adjustment: {original_remaining} → {history_entry.remaining_quantity}. {notes}",
            created_by=current_user.id if current_user.is_authenticated else None,
            quantity_used=quantity if change_type in ['spoil', 'trash', 'damage'] else 0.0,
            sale_location='manual',
            organization_id=current_user.organization_id if current_user.is_authenticated else 1  # Default to org 1 if no user
        )

        db.session.add(adjustment_history)
        return True

    @staticmethod
    def process_return_credit(sku_id: int, quantity: float, original_batch_id: Optional[int] = None,
                            notes: str = '', sale_price: Optional[float] = None) -> bool:
        """Process returns by crediting back to original FIFO entries"""

        sku = ProductSKU.query.get_or_404(sku_id)

        if original_batch_id:
            # Find original deductions for this batch by looking for sales with specific batch reference
            from ..models import Batch
            batch = Batch.query.get(original_batch_id)
            batch_label = batch.label_code if batch else f"BATCH{original_batch_id}"

            # Find deductions that reference this batch's label as fifo_source
            original_deductions = ProductSKUHistory.query.filter(
                ProductSKUHistory.sku_id == sku_id,
                ProductSKUHistory.change_type == 'sale',
                ProductSKUHistory.quantity_change < 0,
                ProductSKUHistory.fifo_reference_id.isnot(None)
            ).join(
                ProductSKUHistory.fifo_reference,
                ProductSKUHistory.fifo_reference_id == ProductSKUHistory.id
            ).filter(
                ProductSKUHistory.fifo_source == batch_label
            ).order_by(ProductSKUHistory.timestamp.desc()).all()

            remaining_to_credit = quantity

            # Credit back to original FIFO entries
            for deduction in original_deductions:
                if remaining_to_credit <= 0:
                    break

                original_fifo_entry = ProductSKUHistory.query.get(deduction.fifo_reference_id)
                if original_fifo_entry:
                    credit_amount = min(remaining_to_credit, abs(deduction.quantity_change))

                    # Credit back to original FIFO entry
                    original_fifo_entry.remaining_quantity += credit_amount
                    remaining_to_credit -= credit_amount

                    # Create credit history
                    credit_history = ProductSKUHistory(
                        sku_id=sku_id,
                        timestamp=datetime.utcnow(),
                        change_type='refunded',
                        quantity_change=credit_amount,
                        old_quantity=sku.current_quantity,
                        new_quantity=sku.current_quantity + credit_amount,
                        remaining_quantity=0,  # Credits don't create new FIFO entries
                        unit=sku.unit,
                        unit_cost=original_fifo_entry.unit_cost,
                        sale_price=sale_price,
                        fifo_code=generate_fifo_id('refunded'),  
                        fifo_reference_id=original_fifo_entry.id,
                        fifo_source=original_fifo_entry.fifo_source,
                        notes=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                        note=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                        created_by=current_user.id if current_user.is_authenticated else None,
                        quantity_used=0.0,
                        sale_location='manual',
                        organization_id=current_user.organization_id if current_user.is_authenticated else None
                    )
                    db.session.add(credit_history)

            # Handle any remaining quantity as new stock
            if remaining_to_credit > 0:
                ProductInventoryService.add_stock(
                    sku_id=sku_id,
                    quantity=remaining_to_credit,
                    unit_cost=sku.unit_cost or 0,
                    change_type='restock',
                    notes=f"{notes} (Excess return - no original FIFO found)"
                )
        else:
            # Simple addition for returns without batch tracking
            ProductInventoryService.add_stock(
                sku_id=sku_id,
                quantity=quantity,
                unit_cost=sku.unit_cost or 0,
                change_type='refunded',
                notes=notes,
                sale_price=sale_price
            )

        return True

    @staticmethod
    def reserve_stock(sku_id: int, quantity: float, order_id: str, reservation_id: str) -> bool:
        """Reserve stock for pending orders"""
        sku = ProductSKU.query.get_or_404(sku_id)

        if sku.available_for_sale < quantity:
            return False

        sku.reserved_quantity = (sku.reserved_quantity or 0) + quantity

        # Create reservation history
        history = ProductSKUHistory(
            sku_id=sku_id,
            timestamp=datetime.utcnow(),
            change_type='reserved',
            quantity_change=0,  # No actual quantity change
            old_quantity=sku.current_quantity,
            new_quantity=sku.current_quantity,
            remaining_quantity=0,
            unit=sku.unit,
            unit_cost=sku.unit_cost,
            order_id=order_id,
            reservation_id=reservation_id,
            is_reserved=True,
            notes=f"Reserved {quantity} {sku.unit} for order {order_id}",
            note=f"Reserved {quantity} {sku.unit} for order {order_id}",
            created_by=current_user.id if current_user.is_authenticated else None,
            quantity_used=0.0,
            sale_location='pos',
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )
        db.session.add(history)
        return True

    @staticmethod
    def get_sku_history(sku_id: int, page: int = 1, per_page: int = 50) -> dict:
        """Get paginated history for SKU"""

        history_query = ProductSKUHistory.query.filter_by(sku_id=sku_id)\
            .order_by(ProductSKUHistory.timestamp.desc())

        pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'items': pagination.items,
            'pagination': pagination,
            'total': pagination.total
        }

    @staticmethod
    def get_fifo_entries(sku_id: int, active_only: bool = False):
        """Get FIFO entries for SKU - from history entries with remaining_quantity"""
        query = ProductSKUHistory.query.filter_by(sku_id=sku_id)

        if active_only:
            query = query.filter(ProductSKUHistory.remaining_quantity > 0)
        else:
            # Show entries that were additions (have remaining_quantity field populated)
            query = query.filter(ProductSKUHistory.original_quantity.isnot(None))

        return query.order_by(ProductSKUHistory.timestamp.asc()).all()

    @staticmethod
    def get_all_skus_summary() -> List[Dict]:
        """Get summary of all SKUs with current quantities"""
        skus = ProductSKU.query.filter_by(is_active=True).all()

        summary = []
        for sku in skus:
            summary.append({
                'sku_id': sku.id,
                'product_name': sku.product_name,
                'variant_name': sku.variant_name,
                'size_label': sku.size_label,
                'sku_code': sku.sku_code,
                'current_quantity': sku.current_quantity,
                'reserved_quantity': sku.reserved_quantity or 0,
                'available_quantity': sku.available_for_sale,
                'unit': sku.unit,
                'unit_cost': sku.unit_cost,
                'low_stock_threshold': sku.low_stock_threshold,
                'is_low_stock': sku.current_quantity <= sku.low_stock_threshold
            })

        return summary

    @staticmethod
    def validate_sku_fifo_sync(sku_id: int):
        """Validate that SKU quantity matches sum of FIFO remaining quantities"""
        sku = ProductSKU.query.get(sku_id)
        if not sku:
            return False, "SKU not found", 0, 0

        fifo_entries = ProductInventoryService.get_fifo_entries(sku_id, active_only=True)
        fifo_total = sum(entry.remaining_quantity for entry in fifo_entries)

        # Allow small floating point differences (0.001)
        if abs(sku.current_quantity - fifo_total) > 0.001:
            error_msg = f"SYNC ERROR: SKU {sku.display_name} quantity ({sku.current_quantity}) != FIFO total ({fifo_total})"
            return False, error_msg, sku.current_quantity, fifo_total

        return True, "", sku.current_quantity, fifo_total