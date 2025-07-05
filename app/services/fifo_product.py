
from datetime import datetime
from flask_login import current_user
from ..models import db, ProductSKU, ProductSKUHistory
from ..utils.fifo_generator import generate_fifo_id
from .history_logger import HistoryLogger

class ProductFIFOService:
    """FIFO operations specifically for Product SKUs"""
    
    @staticmethod
    def handle_recount(sku_id, target_quantity, unit, notes=None, cost_override=None, 
                      custom_expiration_date=None, custom_shelf_life_days=None):
        """
        Handle recount operations with proper FIFO sync for product SKUs
        Mirrors the raw inventory recount logic exactly
        """
        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("SKU not found")
        
        current_qty = sku.current_quantity
        qty_difference = target_quantity - current_qty
        
        if qty_difference == 0:
            # No change needed
            return True, "Recount completed - no adjustment needed"
        
        elif qty_difference > 0:
            # Adding inventory - fill existing lots first, then create new ones
            return ProductFIFOService._handle_recount_increase(
                sku, qty_difference, unit, notes, cost_override,
                custom_expiration_date, custom_shelf_life_days, target_quantity
            )
        
        else:
            # Reducing inventory - deduct from all available lots
            return ProductFIFOService._handle_recount_decrease(
                sku, abs(qty_difference), unit, notes, target_quantity
            )
    
    @staticmethod
    def _handle_recount_increase(sku, qty_to_add, unit, notes, cost_override, 
                               custom_expiration_date, custom_shelf_life_days, target_quantity):
        """Handle recount increases by filling existing lots then creating new ones"""
        # Find existing unfilled lots
        existing_entries = ProductSKUHistory.query.filter(
            ProductSKUHistory.sku_id == sku.id,
            ProductSKUHistory.remaining_quantity < ProductSKUHistory.quantity_change,
            ProductSKUHistory.quantity_change > 0
        ).order_by(ProductSKUHistory.timestamp.asc()).all()
        
        remaining_to_add = qty_to_add
        
        # Fill existing unfilled lots first
        for entry in existing_entries:
            if remaining_to_add <= 0:
                break
            
            can_fill = entry.quantity_change - entry.remaining_quantity
            if can_fill > 0:
                fill_amount = min(can_fill, remaining_to_add)
                entry.remaining_quantity += fill_amount
                remaining_to_add -= fill_amount
        
        # Create new lot for any remaining quantity
        if remaining_to_add > 0:
            HistoryLogger.record_product_sku_history(
                sku_id=sku.id,
                change_type='recount',
                quantity_change=remaining_to_add,
                unit=unit,
                remaining_quantity=remaining_to_add,
                unit_cost=cost_override or sku.cost_per_unit,
                notes=notes or 'Recount adjustment - quantity increase',
                fifo_code=generate_fifo_id('recount'),
                expiration_date=custom_expiration_date,
                shelf_life_days=custom_shelf_life_days,
                is_perishable=custom_expiration_date is not None
            )
        
        # Update SKU quantity
        sku.inventory_item.quantity = target_quantity
        if cost_override:
            sku.inventory_item.cost_per_unit = cost_override
        
        return True, "Recount completed - inventory increased"
    
    @staticmethod
    def _handle_recount_decrease(sku, qty_to_deduct, unit, notes, target_quantity):
        """Handle recount decreases by deducting from ALL lots (including expired)"""
        # Get ALL entries with remaining quantity (fresh AND expired)
        all_entries_with_remaining = ProductSKUHistory.query.filter(
            ProductSKUHistory.sku_id == sku.id,
            ProductSKUHistory.remaining_quantity > 0
        ).order_by(ProductSKUHistory.timestamp.asc()).all()
        
        remaining_to_deduct = qty_to_deduct
        
        # Deduct from all available lots (fresh and expired)
        for entry in all_entries_with_remaining:
            if remaining_to_deduct <= 0:
                break
            
            deduction = min(entry.remaining_quantity, remaining_to_deduct)
            entry.remaining_quantity -= deduction
            remaining_to_deduct -= deduction
            
            # Create deduction history entry
            HistoryLogger.record_product_sku_history(
                sku_id=sku.id,
                change_type='recount',
                quantity_change=-deduction,
                unit=unit,
                remaining_quantity=0,
                unit_cost=entry.unit_cost,
                notes=f"{notes or 'Recount adjustment'} (From FIFO #{entry.id})",
                fifo_reference_id=entry.id
            )
        
        if remaining_to_deduct > 0:
            # This shouldn't happen in a proper recount
            raise ValueError(f'Recount failed: tried to deduct {qty_to_deduct} but only {qty_to_deduct - remaining_to_deduct} available')
        
        # Update SKU quantity
        sku.inventory_item.quantity = target_quantity
        
        return True, "Recount completed - inventory decreased"
    
    @staticmethod
    def create_initial_stock(sku_id, quantity, unit, notes=None, cost_override=None,
                           custom_expiration_date=None, custom_shelf_life_days=None):
        """Create initial stock for SKU with no history"""
        sku = ProductSKU.query.get(sku_id)
        if not sku:
            raise ValueError("SKU not found")
        
        # Create initial FIFO entry
        HistoryLogger.record_product_sku_history(
            sku_id=sku_id,
            change_type='restock',  # Use restock for initial creation
            quantity_change=quantity,
            unit=unit,
            remaining_quantity=quantity,
            unit_cost=cost_override or sku.cost_per_unit,
            notes=notes or 'Initial stock creation via recount',
            fifo_code=generate_fifo_id('restock'),
            expiration_date=custom_expiration_date,
            shelf_life_days=custom_shelf_life_days,
            is_perishable=custom_expiration_date is not None
        )
        
        # Update SKU quantity through inventory_item
        sku.inventory_item.quantity = quantity
        if cost_override:
            sku.inventory_item.cost_per_unit = cost_override
        
        return True, 'Initial SKU inventory created successfully'
