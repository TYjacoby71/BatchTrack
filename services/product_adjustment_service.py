from models import db, ProductInventory, ProductInventoryHistory, Product, ProductEvent
from datetime import datetime
from services.inventory_adjustment import process_inventory_adjustment, generate_fifo_code

class ProductAdjustmentService:
    """Simplified service that delegates to centralized inventory_adjustment service"""

    @staticmethod
    def add_manual_stock(product_id, variant_name, container_id, quantity, unit_cost=0, notes=''):
        """Add manual stock - delegates to centralized service"""
        from models import InventoryItem

        product = Product.query.get_or_404(product_id)
        container = InventoryItem.query.get_or_404(container_id) if container_id else None

        # Create size label from container or use product-based labeling
        if container:
            size_label = f"{container.storage_amount} {container.storage_unit} {container.name.replace('Container - ', '')}"
        else:
            size_label = f"Whole {product.name}" if product.product_base_unit in ['each', 'count', 'loaf', 'item'] else f"Bulk {product.name}"

        # Create ProductInventory entry
        inventory = ProductInventory(
            product_id=product_id,
            variant=variant_name or 'Base',
            size_label=size_label,
            unit='count',
            quantity=quantity,
            container_id=container_id,
            batch_cost_per_unit=unit_cost,
            timestamp=datetime.utcnow(),
            notes=notes
        )

        db.session.add(inventory)
        db.session.flush()  # Get ID

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
        """Process product inventory adjustments - delegates to centralized service"""
        inventory = ProductInventory.query.get_or_404(inventory_id)

        try:
            if adjustment_type == 'recount':
                # For recount, set absolute quantity
                old_quantity = inventory.quantity
                inventory.quantity = quantity
                quantity_change = quantity - old_quantity

                # Log the change
                event_note = f"Recount: {old_quantity} → {quantity}"
                if notes:
                    event_note += f". Notes: {notes}"

            elif adjustment_type in ['sold', 'spoil', 'trash', 'tester', 'damaged']:
                # For deductions, use negative quantity
                if inventory.quantity < quantity:
                    raise ValueError("Insufficient stock for deduction")

                inventory.quantity -= quantity
                quantity_change = -quantity

                event_note = f"{adjustment_type.title()}: {quantity} units"
                if notes:
                    event_note += f". Notes: {notes}"
            else:
                # For additions
                inventory.quantity += quantity
                quantity_change = quantity

                event_note = f"{adjustment_type.title()}: {quantity} units added"
                if notes:
                    event_note += f". Notes: {notes}"

            # Create history entry
            history = ProductInventoryHistory(
                product_inventory_id=inventory_id,
                change_type=adjustment_type,
                quantity_change=quantity_change,
                unit=inventory.unit,
                remaining_quantity=inventory.quantity if quantity_change > 0 else None,
                note=event_note,
                created_by=1  # TODO: Get current user
            )

            db.session.add(history)

            # Log product event
            db.session.add(ProductEvent(
                product_id=inventory.product_id,
                event_type=f'inventory_{adjustment_type}',
                note=event_note
            ))

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Adjustment failed: {str(e)}")