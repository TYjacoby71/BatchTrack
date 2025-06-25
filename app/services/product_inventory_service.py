
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from flask_login import current_user
from sqlalchemy import func, desc, asc

from ..models import db, Product, ProductVariation, ProductSKU, ProductInventory, ProductInventoryHistory, ProductEvent
from ..services.inventory_adjustment import generate_fifo_code

class ProductInventoryService:
    """Unified service for all product inventory operations - mirrors inventory_adjustment.py"""
    
    @staticmethod
    def get_or_create_sku(product_id: int, variant_name: str, size_label: str, unit: str = 'count') -> ProductSKU:
        """Get or create SKU entity - like getting an InventoryItem"""
        
        # Get or create variant
        variant = ProductVariation.query.filter_by(
            product_id=product_id,
            name=variant_name
        ).first()
        
        if not variant:
            variant = ProductVariation(
                product_id=product_id,
                name=variant_name
            )
            db.session.add(variant)
            db.session.flush()
        
        # Get or create SKU
        sku = ProductSKU.query.filter_by(
            product_id=product_id,
            variant_id=variant.id,
            size_label=size_label
        ).first()
        
        if not sku:
            sku = ProductSKU(
                product_id=product_id,
                variant_id=variant.id,
                variant_name=variant_name,
                size_label=size_label,
                unit=unit,
                created_by=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(sku)
            db.session.flush()
            
        return sku
    
    @staticmethod
    def add_stock(sku_id: int, quantity: float, unit_cost: float = 0, 
                  batch_id: Optional[int] = None, container_id: Optional[int] = None,
                  notes: str = '', change_type: str = 'manual_addition') -> ProductInventory:
        """Add stock to SKU - like adding to InventoryHistory with remaining_quantity"""
        
        sku = ProductSKU.query.get_or_404(sku_id)
        
        # Create FIFO entry (like InventoryHistory with remaining_quantity)
        fifo_entry = ProductInventory(
            sku_id=sku_id,
            product_id=sku.product_id,
            variant_id=sku.variant_id,
            variant=sku.variant_name,
            size_label=sku.size_label,
            quantity=quantity,
            unit=sku.unit,
            batch_id=batch_id,
            container_id=container_id,
            batch_cost_per_unit=unit_cost,
            timestamp=datetime.utcnow(),
            notes=notes
        )
        db.session.add(fifo_entry)
        db.session.flush()
        
        # Create history entry
        history = ProductInventoryHistory(
            sku_id=sku_id,
            product_inventory_id=fifo_entry.id,
            change_type=change_type,
            quantity_change=quantity,
            unit=sku.unit,
            remaining_quantity=quantity,
            unit_cost=unit_cost,
            fifo_code=generate_fifo_code(f"SKU{sku_id}"),
            note=notes,
            created_by=current_user.id if current_user.is_authenticated else None,
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        
        # Log product event
        db.session.add(ProductEvent(
            product_id=sku.product_id,
            event_type=f'inventory_{change_type}',
            description=f"{change_type.replace('_', ' ').title()}: {quantity} {sku.unit} added to {sku.variant_name} - {sku.size_label}"
        ))
        
        return fifo_entry
    
    @staticmethod
    def deduct_stock(sku_id: int, quantity: float, change_type: str = 'sale',
                     notes: str = '', sale_price: Optional[float] = None,
                     customer: Optional[str] = None) -> bool:
        """Deduct stock using FIFO - mirrors deduct_fifo from inventory_adjustment"""
        
        sku = ProductSKU.query.get_or_404(sku_id)
        
        # Get FIFO entries with remaining quantity
        fifo_entries = ProductInventory.query.filter_by(sku_id=sku_id)\
            .filter(ProductInventory.quantity > 0)\
            .order_by(ProductInventory.timestamp.asc()).all()
        
        # Check if enough stock available
        total_available = sum(entry.quantity for entry in fifo_entries)
        if total_available < quantity:
            return False
        
        remaining_to_deduct = quantity
        deduction_plan = []
        
        # Plan deductions
        for entry in fifo_entries:
            if remaining_to_deduct <= 0:
                break
                
            deduct_amount = min(entry.quantity, remaining_to_deduct)
            deduction_plan.append((entry, deduct_amount))
            remaining_to_deduct -= deduct_amount
        
        # Execute deductions
        for entry, deduct_amount in deduction_plan:
            entry.quantity -= deduct_amount
            
            # Create history entry for this deduction
            history = ProductInventoryHistory(
                sku_id=sku_id,
                product_inventory_id=entry.id,
                change_type=change_type,
                quantity_change=-deduct_amount,
                unit=sku.unit,
                remaining_quantity=entry.quantity,
                unit_cost=entry.batch_cost_per_unit,
                fifo_code=generate_fifo_code(f"SKU{sku_id}"),
                note=f"{change_type} from FIFO entry #{entry.id}. {notes}",
                created_by=current_user.id if current_user.is_authenticated else None,
                timestamp=datetime.utcnow()
            )
            db.session.add(history)
        
        # Create event note
        if change_type == 'sale' and sale_price and customer:
            event_note = f"Sale: {quantity} {sku.unit} for ${sale_price} to {customer}"
        elif change_type == 'sale' and sale_price:
            event_note = f"Sale: {quantity} {sku.unit} for ${sale_price}"
        else:
            event_note = f"{change_type.replace('_', ' ').title()}: {quantity} {sku.unit}"
        
        if notes:
            event_note += f". {notes}"
            
        db.session.add(ProductEvent(
            product_id=sku.product_id,
            event_type=f'inventory_{change_type}',
            description=event_note
        ))
        
        return True
    
    @staticmethod
    def recount_stock(sku_id: int, new_total: float, notes: str = '') -> bool:
        """Recount SKU stock - mirrors recount_fifo"""
        
        sku = ProductSKU.query.get_or_404(sku_id)
        current_total = sku.current_quantity
        difference = new_total - current_total
        
        if difference == 0:
            return True
            
        if difference < 0:
            # Reduce stock using FIFO
            return ProductInventoryService.deduct_stock(
                sku_id=sku_id,
                quantity=abs(difference),
                change_type='recount',
                notes=f"Recount adjustment: {current_total} → {new_total}. {notes}"
            )
        else:
            # Add stock
            ProductInventoryService.add_stock(
                sku_id=sku_id,
                quantity=difference,
                change_type='recount',
                notes=f"Recount adjustment: {current_total} → {new_total}. {notes}"
            )
            return True
    
    @staticmethod
    def adjust_fifo_entry(inventory_id: int, quantity: float, change_type: str,
                         notes: str = '') -> bool:
        """Adjust specific FIFO entry - like adjusting specific InventoryHistory entry"""
        
        fifo_entry = ProductInventory.query.get_or_404(inventory_id)
        sku = ProductSKU.query.get_or_404(fifo_entry.sku_id)
        
        original_quantity = fifo_entry.quantity
        
        if change_type == 'recount':
            # Set new total for this entry
            quantity_change = quantity - original_quantity
            fifo_entry.quantity = max(0, quantity)
        else:
            # Deduction from this specific entry
            if quantity > original_quantity:
                return False  # Can't deduct more than available
            quantity_change = -quantity
            fifo_entry.quantity = max(0, original_quantity - quantity)
        
        # Create history entry
        history = ProductInventoryHistory(
            sku_id=fifo_entry.sku_id,
            product_inventory_id=inventory_id,
            change_type=change_type,
            quantity_change=quantity_change,
            unit=sku.unit,
            remaining_quantity=fifo_entry.quantity,
            unit_cost=fifo_entry.batch_cost_per_unit,
            fifo_code=generate_fifo_code(f"SKU{fifo_entry.sku_id}"),
            note=f"FIFO entry adjustment: {original_quantity} → {fifo_entry.quantity}. {notes}",
            created_by=current_user.id if current_user.is_authenticated else None,
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        
        return True
    
    @staticmethod
    def get_sku_history(sku_id: int, page: int = 1, per_page: int = 50) -> dict:
        """Get paginated history for SKU - like getting InventoryHistory for an item"""
        
        history_query = ProductInventoryHistory.query.filter_by(sku_id=sku_id)\
            .order_by(ProductInventoryHistory.timestamp.desc())
        
        pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': pagination.items,
            'pagination': pagination,
            'total': pagination.total
        }
    
    @staticmethod
    def get_fifo_entries(sku_id: int, active_only: bool = False):
        """Get FIFO entries for SKU"""
        query = ProductInventory.query.filter_by(sku_id=sku_id)
        
        if active_only:
            query = query.filter(ProductInventory.quantity > 0)
            
        return query.order_by(ProductInventory.timestamp.asc()).all()
    
    @staticmethod
    def get_all_skus_summary() -> List[Dict]:
        """Get summary of all SKUs with current quantities"""
        skus = ProductSKU.query.filter_by(is_active=True).all()
        
        summary = []
        for sku in skus:
            summary.append({
                'sku_id': sku.id,
                'product_name': sku.product.name,
                'variant_name': sku.variant_name,
                'size_label': sku.size_label,
                'sku_code': sku.sku_code,
                'current_quantity': sku.current_quantity,
                'unit': sku.unit,
                'low_stock_threshold': sku.low_stock_threshold,
                'is_low_stock': sku.current_quantity <= sku.low_stock_threshold
            })
            
        return summary
