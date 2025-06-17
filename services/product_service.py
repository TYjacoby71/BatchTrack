from sqlalchemy import func
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Product, ProductInventory, ProductEvent, ProductInventoryHistory, Batch, InventoryItem
from app.extensions import db
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from services.inventory_adjustment import generate_fifo_code
from flask_login import current_user

def adjust_product_fifo_entry(fifo_entry_id, quantity, change_type, notes=None, created_by=None):
    """
    Adjust a specific FIFO entry's remaining quantity for product inventory
    Args:
        fifo_entry_id: ID of the ProductInventory FIFO entry
        quantity: Amount to adjust (for recount: new total, for deductions: negative amount)
        change_type: Type of change (recount, sale, spoil, damage, trash, gift/tester)
        notes: Optional notes
        created_by: User ID who created the change
    Returns:
        bool: Success status
    """
    try:
        # Get the original FIFO entry (ProductInventory, not ProductInventoryHistory)
        fifo_entry = ProductInventory.query.get(fifo_entry_id)
        if not fifo_entry:
            raise ValueError("FIFO entry not found")

        original_quantity = fifo_entry.quantity

        if change_type == 'recount':
            # For recount, quantity is the new total
            quantity_change = quantity - original_quantity
            fifo_entry.quantity = quantity
        else:
            # For deductions, quantity should be negative
            quantity_change = quantity
            if quantity_change >= 0:
                raise ValueError("Deduction quantity must be negative")

            # Validate quantity doesn't exceed available
            if abs(quantity_change) > original_quantity:
                raise ValueError("Cannot adjust more than available quantity")

            fifo_entry.quantity += quantity_change

        # Ensure quantity doesn't go negative
        if fifo_entry.quantity < 0:
            fifo_entry.quantity = 0

        # Create adjustment event
        event_note = f"{change_type.title()}: "
        if change_type == 'recount':
            event_note += f"{original_quantity} → {fifo_entry.quantity} ({quantity_change:+.2f}) for {fifo_entry.size_label}"
        else:
            event_note += f"{abs(quantity_change)} × {fifo_entry.size_label}"

        if fifo_entry.variant and fifo_entry.variant != 'Base':
            event_note += f" ({fifo_entry.variant})"
        if notes:
            event_note += f". Notes: {notes}"

        db.session.add(ProductEvent(
            product_id=fifo_entry.product_id,
            event_type=f'inventory_{change_type}',
            note=event_note
        ))

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        raise e

class ProductService:
    """Unified service for all product inventory operations"""

    @staticmethod
    def generate_product_fifo_code(product_id):
        """Generate base32 FIFO code with product prefix"""
        product = Product.query.get(product_id)
        prefix = product.name[:3].upper() if product else "PRD"
        return generate_fifo_code(prefix)

    @staticmethod
    def add_product_from_batch(batch_id: int, product_id: int, variant_label: Optional[str] = None, 
                             size_label: Optional[str] = None, quantity: float = None, 
                             container_id: Optional[int] = None, 
                             container_overrides: Optional[Dict[int, int]] = None) -> List[ProductInventory]:
        """Add product inventory from a finished batch, creating SKU-level entries that aggregate upward"""
        from app.models import BatchContainer, InventoryItem

        batch = Batch.query.get_or_404(batch_id)
        product = Product.query.get_or_404(product_id)

        inventory_entries = []

        # Get containers used in this batch
        batch_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()

        if batch_containers:
            # Create separate SKU-level inventory entries for each container type
            for container_usage in batch_containers:
                container = container_usage.container
                # SKU-level size_label: This is the atomic unit that everything aggregates from
                sku_size_label = f"{container.storage_amount} {container.storage_unit} {container.name.replace('Container - ', '')}"

                # Use override count if provided, otherwise use calculated amount
                final_count = container_usage.quantity_used
                if container_overrides and container.id in container_overrides:
                    final_count = container_overrides[container.id]

                # Calculate cost per unit for this specific batch
                batch_cost_per_unit = None
                if batch.total_cost and batch.final_quantity:
                    batch_cost_per_unit = batch.total_cost / batch.final_quantity

                # Create SKU-level entry - this is the source of truth
                inventory = ProductInventory(
                    product_id=product_id,
                    batch_id=batch_id,
                    variant=variant_label or 'Base',
                    size_label=sku_size_label,
                    sku=None,  # SKU can be assigned later at the SKU view level
                    unit='count',  # Container units are typically counted
                    quantity=final_count,
                    container_id=container.id,
                    batch_cost_per_unit=batch_cost_per_unit,
                    timestamp=datetime.utcnow(),
                    expiration_date=batch.expiration_date.date() if batch.expiration_date else None,
                    notes=f"SKU entry from batch #{batch.id} - {container.name} (final count: {final_count})"
                )

                db.session.add(inventory)
                inventory_entries.append(inventory)

                # Log product event with SKU context
                event_note = f"Added {final_count} × {sku_size_label} SKU"
                if variant_label:
                    event_note += f" ({variant_label})"
                event_note += f" from batch #{batch.id}"

                db.session.add(ProductEvent(
                    product_id=product_id,
                    event_type='inventory_addition',
                    note=event_note
                ))
        else:
            # Fallback to bulk SKU for non-containerized batches
            batch_unit = batch.output_unit or batch.projected_yield_unit or 'oz'
            quantity_used = quantity or batch.final_quantity or batch.projected_yield

            # Convert to product base unit if different
            if batch_unit != product.product_base_unit:
                try:
                    from services.unit_conversion import convert_unit
                    converted_quantity = convert_unit(quantity_used, batch_unit, product.product_base_unit)
                    unit = product.product_base_unit
                    quantity_used = converted_quantity
                    conversion_note = f" (converted from {quantity_used} {batch_unit})"
                except Exception as e:
                    # If conversion fails, use batch unit as-is
                    unit = batch_unit
                    conversion_note = f" (conversion from {batch_unit} to {product.product_base_unit} failed: {str(e)})"
            else:
                unit = product.product_base_unit
                conversion_note = ""

            # Calculate cost per unit for this specific batch
            batch_cost_per_unit = None
            if batch.total_cost and batch.final_quantity:
                batch_cost_per_unit = batch.total_cost / batch.final_quantity

            # Create bulk SKU entry - still the atomic source of truth
            sku_size_label = "Bulk"

            inventory = ProductInventory(
                product_id=product_id,
                batch_id=batch_id,
                variant=variant_label or 'Base',
                size_label=sku_size_label,
                sku=None,  # SKU can be assigned later
                unit=unit,
                quantity=quantity_used,
                batch_cost_per_unit=batch_cost_per_unit,
                timestamp=datetime.utcnow(),
                expiration_date=batch.expiration_date.date() if batch.expiration_date else None,
                notes=f"Bulk SKU entry from batch #{batch.id}{conversion_note}"
            )

            db.session.add(inventory)
            inventory_entries.append(inventory)

            # Log product event with SKU context
            event_note = f"Added {quantity_used} {unit} bulk SKU"
            if variant_label:
                event_note += f" ({variant_label})"
            event_note += f" from batch #{batch.id}{conversion_note}"

            db.session.add(ProductEvent(
                product_id=product_id,
                event_type='inventory_addition',
                note=event_note
            ))

        return inventory_entries

    @staticmethod
    def process_inventory_adjustment(product_id, variant, size_label, adjustment_type, quantity, 
                                   notes='', sale_price=None, customer=None, unit_cost=None):
        """Process all types of product inventory adjustments"""

        if adjustment_type == 'recount':
            return ProductService.process_recount(product_id, variant, size_label, quantity, notes)
        elif adjustment_type == 'manual_add':
            return ProductService.add_manual_stock(product_id, variant, None, quantity, unit_cost or 0, notes, size_label)
        else:
            # Handle deductions: sale, spoil, trash, damaged, sample
            return ProductService.process_deduction(product_id, variant, size_label, adjustment_type, 
                                                  quantity, notes, sale_price, customer)

    @staticmethod
    def process_deduction(product_id, variant, size_label, reason, quantity, notes='', sale_price=None, customer=None):
        """Process product deductions using FIFO"""

        # Get FIFO-ordered inventory for this SKU combination
        inventory_items = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant,
            size_label=size_label
        ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

        # Check if enough stock is available
        total_available = sum(item.quantity for item in inventory_items)
        if total_available < quantity:
            return False

        remaining_to_deduct = quantity
        deducted_items = []

        for item in inventory_items:
            if remaining_to_deduct <= 0:
                break

            if item.quantity <= remaining_to_deduct:
                # Use entire item
                deducted_items.append((item, item.quantity))
                remaining_to_deduct -= item.quantity
                item.quantity = 0
            else:
                # Partial use
                deducted_items.append((item, remaining_to_deduct))
                item.quantity -= remaining_to_deduct
                remaining_to_deduct = 0

        # Create structured event note based on reason
        if reason == 'sale' and sale_price and customer:
            event_note = f"Sale: {quantity} × {size_label} for ${sale_price} (${sale_price/quantity:.2f}/unit) to {customer}"
        elif reason == 'sale' and sale_price:
            event_note = f"Sale: {quantity} × {size_label} for ${sale_price} (${sale_price/quantity:.2f}/unit)"
        elif reason == 'sample':
            event_note = f"Sample/Gift: {quantity} × {size_label}"
        else:
            event_note = f"{reason.title()}: {quantity} × {size_label}"

        if variant and variant != 'Base':
            event_note += f" ({variant})"
        if notes:
            event_note += f". Notes: {notes}"

        db.session.add(ProductEvent(
            product_id=product_id,
            event_type=f'inventory_{reason}',
            note=event_note
        ))

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
                    entry.quantity = 0

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

        # Log the recount event
        event_note = f"Recount: {current_total} → {new_total} ({quantity_change:+.2f}) for {size_label}"
        if variant and variant != 'Base':
            event_note += f" ({variant})"
        if notes:
            event_note += f". Notes: {notes}"

        db.session.add(ProductEvent(
            product_id=product_id,
            event_type='inventory_recount',
            note=event_note
        ))

        db.session.commit()
        return True

    @staticmethod
    def add_manual_stock(product_id, variant_name, container_id, quantity, unit_cost=0, notes='', size_label=None):
        """Add manual stock with container matching"""
        from app.models import InventoryItem

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

        # Log product event
        if container:
            event_note = f"Manual addition: {quantity} × {final_size_label}"
        else:
            event_note = f"Manual addition: {quantity} {product.product_base_unit} of {final_size_label}"

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
    def get_product_variant_summary():
        """Get a summary of all active product inventory grouped by product, variant, size and unit"""
        results = db.session.query(
            ProductInventory.product_id,
            Product.name,
            ProductInventory.variant,
            ProductInventory.size_label, 
            ProductInventory.unit,
            func.sum(ProductInventory.quantity).label("total_quantity")
        ).join(Product).filter(
            ProductInventory.quantity > 0
        ).group_by(
            ProductInventory.product_id,
            ProductInventory.variant,
            ProductInventory.size_label,
            ProductInventory.unit,
            Product.name
        ).all()

        return results

    @staticmethod
    def get_product_summary():
        """Get summary of all products with inventory totals"""
        products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
        return products

    @staticmethod
    def get_fifo_inventory_groups(product_id):
        """Get FIFO inventory grouped by variant and size for product view"""
        inventory_entries = ProductInventory.query.filter_by(
            product_id=product_id
        ).filter(ProductInventory.quantity > 0).order_by(
            ProductInventory.variant, 
            ProductInventory.size_label,
            ProductInventory.timestamp.asc()
        ).all()

        # Group by variant and size_label
        groups = {}
        for entry in inventory_entries:
            key = f"{entry.variant}_{entry.size_label}"
            if key not in groups:
                groups[key] = {
                    'variant': entry.variant,
                    'size_label': entry.size_label,
                    'unit': entry.unit,
                    'total_quantity': 0,
                    'batches': []
                }
            groups[key]['total_quantity'] += entry.quantity
            groups[key]['batches'].append(entry)

        return groups