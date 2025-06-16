from models import db, ProductInventory, ProductInventoryHistory, Product, ProductEvent
from datetime import datetime
from services.inventory_adjustment import generate_fifo_code
import base64
from flask_login import current_user

class ProductAdjustmentService:
    """Service for handling all product inventory adjustments with FIFO tracking"""

    @staticmethod
    def generate_product_fifo_code(product_id):
        """Generate base32 FIFO code with product prefix"""
        product = Product.query.get(product_id)
        prefix = product.name[:3].upper() if product else "PRD"
        return generate_fifo_code(prefix)

    @staticmethod
    def add_manual_stock(product_id, variant_name, container_id, quantity, unit_cost=0, notes='', size_label=None):
        """Add manual stock with container matching"""
        from models import InventoryItem

        product = Product.query.get_or_404(product_id)
        container = InventoryItem.query.get_or_404(container_id) if container_id else None

        # Create size label from container, parameter, or use product-based labeling
        if size_label:
            # Use provided size_label (for SKU-level adjustments)
            final_size_label = size_label
        elif container:
            final_size_label = f"{container.storage_amount} {container.storage_unit} {container.name.replace('Container - ', '')}"
        else:
            # For standalone products without containers, always use "Bulk"
            final_size_label = "Bulk"

        # Create ProductInventory entry
        inventory = ProductInventory(
            product_id=product_id,
            variant=variant_name or 'Base',
            size_label=final_size_label,
            unit='count',
            quantity=quantity,
            container_id=container_id,
            batch_cost_per_unit=unit_cost,
            timestamp=datetime.utcnow(),
            notes=notes
        )

        db.session.add(inventory)
        db.session.commit()
        return True

    @staticmethod
    def process_recount(product_id, variant, size_label, new_total, notes=''):
        """Process a recount adjustment for a specific SKU combination"""
        
        # Get all current entries for this SKU combination
        current_entries = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant,
            size_label=size_label
        ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()
        
        current_total = sum(entry.quantity for entry in current_entries)
        quantity_change = new_total - current_total
        
        if quantity_change == 0:
            return True  # No change needed
            
        if quantity_change < 0:
            # Need to reduce inventory using FIFO
            remaining_to_deduct = abs(quantity_change)
            
            for entry in current_entries:
                if remaining_to_deduct <= 0:
                    break
                    
                if entry.quantity <= remaining_to_deduct:
                    # Use entire entry
                    remaining_to_deduct -= entry.quantity
                    entry.quantity = 0
                else:
                    # Partial deduction
                    entry.quantity -= remaining_to_deduct
                    remaining_to_deduct = 0
                    
        else:
            # Need to add inventory - create new entry
            inventory = ProductInventory(
                product_id=product_id,
                variant=variant,
                size_label=size_label,
                unit='count',  # Default to count for recounts
                quantity=quantity_change,
                batch_cost_per_unit=0,  # Recounts don't have cost
                timestamp=datetime.utcnow(),
                notes=f"Recount adjustment: +{quantity_change}. {notes}"
            )
            db.session.add(inventory)
            
        db.session.commit()
        return True

        db.session.add(inventory)
        db.session.flush()  # Get ID

        # Create FIFO history entry
        fifo_code = ProductAdjustmentService.generate_product_fifo_code(product_id)
        history = ProductInventoryHistory(
            product_inventory_id=inventory.id,
            change_type='manual_addition',
            quantity_change=quantity,
            unit='count',
            remaining_quantity=quantity,
            unit_cost=unit_cost,
            fifo_code=fifo_code,
            note=notes,
            created_by=current_user.id if current_user.is_authenticated else None
        )

        db.session.add(history)

        # Log product event
        if container:
            event_note = f"Manual addition: {quantity} × {size_label}"
        else:
            event_note = f"Manual addition: {quantity} {product.product_base_unit} of {size_label}"

        if variant_name:
            event_note += f" ({variant_name})"
        if notes:
            event_note += f". Notes: {notes}"

        db.session.add(ProductEvent(
            product_id=product_id,
            event_type='inventory_manual_addition',
            note=event_note
        ))

        db.session.commit()
        return inventory

    @staticmethod
    def process_adjustment(inventory_id, adjustment_type, quantity, notes=''):
        """Process product inventory adjustments with FIFO tracking"""
        inventory = ProductInventory.query.get_or_404(inventory_id)

        if adjustment_type == 'recount':
            # Direct quantity change
            old_quantity = inventory.quantity
            quantity_change = quantity - old_quantity
            inventory.quantity = quantity

            # Create history entry
            history = ProductInventoryHistory(
                product_inventory_id=inventory_id,
                change_type=adjustment_type,
                quantity_change=quantity_change,
                unit=inventory.unit,
                remaining_quantity=quantity if quantity_change > 0 else None,
                note=f"Recount: {old_quantity} → {quantity}. {notes}",
                created_by=current_user.id if current_user.is_authenticated else None
            )

            db.session.add(history)

        elif adjustment_type in ['sold', 'spoil', 'trash', 'tester', 'damaged']:
            # FIFO deduction
            success = ProductAdjustmentService.deduct_fifo(
                inventory_id, quantity, adjustment_type, notes
            )
            if not success:
                raise ValueError("Insufficient stock for deduction")

        # Log product event
        event_note = f"{adjustment_type.title()}: "
        if adjustment_type == 'recount':
            event_note += f"Quantity adjusted to {quantity}"
        else:
            event_note += f"{quantity} units"

        if notes:
            event_note += f". Notes: {notes}"

        db.session.add(ProductEvent(
            product_id=inventory.product_id,
            event_type=f'inventory_{adjustment_type}',
            note=event_note
        ))

        # Validate FIFO sync after adjustment
        try:
            ProductAdjustmentService.validate_product_fifo_sync(inventory.product_id)
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"FIFO sync validation failed: {str(e)}")

        db.session.commit()
        return True

    @staticmethod
    def validate_product_fifo_sync(product_id):
        """Validate that product FIFO tracking is in sync with actual quantities"""
        product_inventories = ProductInventory.query.filter_by(product_id=product_id).all()

        for inventory in product_inventories:
            # Calculate total remaining from FIFO history
            fifo_total = ProductInventoryHistory.query.filter_by(
                product_inventory_id=inventory.id
            ).filter(
                ProductInventoryHistory.remaining_quantity > 0
            ).with_entities(
                db.func.sum(ProductInventoryHistory.remaining_quantity)
            ).scalar() or 0

            # Compare with actual inventory quantity
            if abs(inventory.quantity - fifo_total) > 0.001:  # Allow for small rounding differences
                raise ValueError(
                    f"FIFO desync detected for inventory {inventory.id}: "
                    f"Actual={inventory.quantity}, FIFO={fifo_total}"
                )

        return True

    @staticmethod
    def deduct_fifo(inventory_id, quantity, reason, notes=''):
        """Deduct using FIFO from specific inventory item's history"""
        inventory = ProductInventory.query.get(inventory_id)

        # Get FIFO entries for this specific inventory item
        fifo_entries = ProductInventoryHistory.query.filter_by(
            product_inventory_id=inventory_id
        ).filter(
            ProductInventoryHistory.remaining_quantity > 0
        ).order_by(ProductInventoryHistory.timestamp.asc()).all()

        # Check available quantity
        total_available = sum(entry.remaining_quantity for entry in fifo_entries)
        if total_available < quantity:
            return False

        remaining_to_deduct = quantity

        for entry in fifo_entries:
            if remaining_to_deduct <= 0:
                break

            if entry.remaining_quantity <= remaining_to_deduct:
                # Use entire entry
                deduction_amount = entry.remaining_quantity
                entry.remaining_quantity = 0
                remaining_to_deduct -= deduction_amount
            else:
                # Partial use
                deduction_amount = remaining_to_deduct
                entry.remaining_quantity -= remaining_to_deduct
                remaining_to_deduct = 0

            # Create deduction history
            deduction_history = ProductInventoryHistory(
                product_inventory_id=inventory_id,
                change_type=reason,
                quantity_change=-deduction_amount,
                unit=inventory.unit,
                remaining_quantity=0,
                fifo_reference_id=entry.id,
                note=f"{reason.title()} deduction from FIFO {entry.fifo_code}. {notes}",
                created_by=current_user.id if current_user.is_authenticated else None
            )

            db.session.add(deduction_history)

        # Update inventory quantity
        inventory.quantity -= quantity

        return True

    @staticmethod
    def get_fifo_summary(inventory_id):
        """Get FIFO summary for an inventory item"""
        fifo_entries = ProductInventoryHistory.query.filter_by(
            product_inventory_id=inventory_id
        ).filter(
            ProductInventoryHistory.remaining_quantity > 0
        ).order_by(ProductInventoryHistory.timestamp.asc()).all()

        total_remaining = sum(entry.remaining_quantity for entry in fifo_entries)
        entry_count = len(fifo_entries)

        return {
            'total_remaining': total_remaining,
            'entry_count': entry_count,
            'entries': fifo_entries
        }