
from sqlalchemy import func
from models import db, ProductInventory, Product, ProductVariation, Batch, ProductEvent
from datetime import datetime
from typing import Optional, Dict, List, Tuple

class ProductInventoryService:
    """Service for handling product inventory operations and batch-to-product transitions"""
    
    @staticmethod
    def add_product_from_batch(batch_id: int, product_id: int, variant_label: Optional[str] = None, 
                             size_label: Optional[str] = None, quantity: float = None) -> ProductInventory:
        """Add product inventory from a finished batch"""
        batch = Batch.query.get_or_404(batch_id)
        product = Product.query.get_or_404(product_id)
        
        # Use batch final quantity if not specified
        if quantity is None:
            quantity = batch.final_quantity or batch.planned_quantity
            
        # Use product default unit if not specified
        unit = product.default_unit
        
        # Create product inventory entry
        inventory = ProductInventory(
            product_id=product_id,
            batch_id=batch_id,
            variant=variant_label,
            quantity=quantity,
            unit=unit,
            timestamp=datetime.utcnow(),
            notes=f"From batch #{batch.id} ({batch.label})"
        )
        
        db.session.add(inventory)
        
        # Log product event
        event_note = f"Added {quantity} {unit}"
        if variant_label:
            event_note += f" ({variant_label})"
        if size_label:
            event_note += f" - {size_label}"
        event_note += f" from batch #{batch.id}"
        
        db.session.add(ProductEvent(
            product_id=product_id,
            event_type='inventory_addition',
            note=event_note
        ))
        
        return inventory
    
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
