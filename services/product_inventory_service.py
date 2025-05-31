
from sqlalchemy import func
from models import db, ProductInventory, Product, ProductVariation, Batch, ProductEvent
from datetime import datetime
from typing import Optional, Dict, List, Tuple

class ProductInventoryService:
    """Service for handling product inventory operations and batch-to-product transitions"""
    
    @staticmethod
    def add_product_from_batch(batch_id: int, product_id: int, variant_label: Optional[str] = None, 
                             size_label: Optional[str] = None, quantity: float = None, 
                             container_id: Optional[int] = None, 
                             container_overrides: Optional[Dict[int, int]] = None) -> List[ProductInventory]:
        """Add product inventory from a finished batch, handling containers as size variants"""
        from models import BatchContainer, InventoryItem
        
        batch = Batch.query.get_or_404(batch_id)
        product = Product.query.get_or_404(product_id)
        
        inventory_entries = []
        
        # Get containers used in this batch
        batch_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
        
        if batch_containers:
            # Create separate inventory entries for each container type
            for container_usage in batch_containers:
                container = container_usage.container
                size_label = f"{container.storage_amount} {container.storage_unit} {container.name.replace('Container - ', '')}"
                
                # Use override count if provided, otherwise use calculated amount
                final_count = container_usage.quantity_used
                if container_overrides and container.id in container_overrides:
                    final_count = container_overrides[container.id]
                
                # Calculate cost per unit for this specific batch
                batch_cost_per_unit = None
                if batch.total_cost and batch.final_quantity:
                    batch_cost_per_unit = batch.total_cost / batch.final_quantity
                
                inventory = ProductInventory(
                    product_id=product_id,
                    batch_id=batch_id,
                    variant=variant_label or 'Default',
                    size_label=size_label,
                    unit='count',  # Container units are typically counted
                    quantity=final_count,
                    container_id=container.id,
                    batch_cost_per_unit=batch_cost_per_unit,
                    timestamp=datetime.utcnow(),
                    notes=f"From batch #{batch.id} using {container.name} (final count: {final_count})"
                )
                
                db.session.add(inventory)
                inventory_entries.append(inventory)
                
                # Log product event
                event_note = f"Added {container_usage.quantity_used} × {size_label}"
                if variant_label:
                    event_note += f" ({variant_label})"
                event_note += f" from batch #{batch.id}"
                
                db.session.add(ProductEvent(
                    product_id=product_id,
                    event_type='inventory_addition',
                    note=event_note
                ))
        else:
            # Fallback to batch output unit if no containers
            unit = product.default_unit
            quantity_used = quantity or batch.final_quantity or batch.projected_yield
            
            # Calculate cost per unit for this specific batch
            batch_cost_per_unit = None
            if batch.total_cost and batch.final_quantity:
                batch_cost_per_unit = batch.total_cost / batch.final_quantity
            
            inventory = ProductInventory(
                product_id=product_id,
                batch_id=batch_id,
                variant=variant_label or 'Default',
                size_label='Bulk',
                unit=unit,
                quantity=quantity_used,
                batch_cost_per_unit=batch_cost_per_unit,
                timestamp=datetime.utcnow(),
                notes=f"From batch #{batch.id} (no containers - bulk output)"
            )
            
            db.session.add(inventory)
            inventory_entries.append(inventory)
            
            # Log product event
            event_note = f"Added {quantity_used} {unit} bulk"
            if variant_label:
                event_note += f" ({variant_label})"
            event_note += f" from batch #{batch.id}"
            
            db.session.add(ProductEvent(
                product_id=product_id,
                event_type='inventory_addition',
                note=event_note
            ))
        
        return inventory_entries
    
    @staticmethod
    def get_fifo_inventory_groups(product_id: int) -> Dict:
        """Get FIFO-ordered inventory grouped by variant and unit"""
        product = Product.query.get_or_404(product_id)
        
        inventory_groups = {}
        for inv in product.inventory:
            if inv.quantity > 0:
                key = f"{inv.variant or 'Default'}_{inv.unit}"
                if key not in inventory_groups:
                    inventory_groups[key] = {
                        'variant': inv.variant or 'Default',
                        'unit': inv.unit,
                        'total_quantity': 0,
                        'batches': [],
                        'avg_cost': 0
                    }
                inventory_groups[key]['batches'].append(inv)
                inventory_groups[key]['total_quantity'] += inv.quantity
        
        # Calculate average weighted cost and sort batches FIFO
        for group in inventory_groups.values():
            total_cost = 0
            total_weight = 0
            
            for inv in group['batches']:
                # Get cost from associated batch if available
                if inv.batch_id:
                    batch = Batch.query.get(inv.batch_id)
                    if batch and batch.total_cost and batch.final_quantity:
                        unit_cost = batch.total_cost / batch.final_quantity
                        total_cost += inv.quantity * unit_cost
                        total_weight += inv.quantity
            
            group['avg_cost'] = total_cost / total_weight if total_weight > 0 else 0
            group['batches'].sort(key=lambda x: x.timestamp)  # FIFO order
        
        return inventory_groups
    
    @staticmethod
    def deduct_fifo(product_id: int, variant_label: str, unit: str, quantity: float, 
                   reason: str = 'manual_deduction', notes: str = '') -> bool:
        """Deduct product inventory using FIFO method"""
        
        # Get FIFO-ordered inventory for this variant
        inventory_items = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant_label,
            unit=unit
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
        
        # Commit the deductions
        db.session.commit()
        
        # Log the event
        event_note = f"FIFO deduction: {quantity} {unit} of {variant_label or 'Default'}. "
        event_note += f"Items used: {len(deducted_items)}. Reason: {reason}"
        if notes:
            event_note += f". Notes: {notes}"
        
        db.session.add(ProductEvent(
            product_id=product_id,
            event_type='inventory_deduction',
            note=event_note
        ))
        db.session.commit()
        
        return True
    
    @staticmethod
    def get_variant_batches(product_id: int, variant_label: str, unit: str) -> List[ProductInventory]:
        """Get FIFO-ordered batches for a specific product variant"""
        return ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant_label,
            unit=unit
        ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()
    
    @staticmethod
    def get_product_summary():
        """Get summary of all products with inventory totals"""
        products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
        
        for product in products:
            product.total_inventory = sum(inv.quantity for inv in product.inventory if inv.quantity > 0)
            product.variant_count = len(product.variations) if hasattr(product, 'variations') else 0
        
        return products
