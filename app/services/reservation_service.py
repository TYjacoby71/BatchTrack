
from flask import current_app
from flask_login import current_user
from ..models import db, InventoryItem, InventoryHistory
from .inventory_adjustment import process_inventory_adjustment
from sqlalchemy import and_

class ReservationService:
    """Service for managing product reservations using separate inventory items"""
    
    @staticmethod
    def get_reserved_item_for_product(product_item_id):
        """Get or create the reserved inventory item for a product"""
        product_item = InventoryItem.query.get(product_item_id)
        if not product_item or product_item.type != 'product':
            return None
        
        reserved_name = f"{product_item.name} (Reserved)"
        reserved_item = InventoryItem.query.filter_by(
            name=reserved_name,
            type='product-reserved',
            organization_id=product_item.organization_id
        ).first()
        
        if not reserved_item:
            reserved_item = InventoryItem(
                name=reserved_name,
                type='product-reserved',
                unit=product_item.unit,
                cost_per_unit=product_item.cost_per_unit,
                quantity=0.0,
                organization_id=product_item.organization_id,
                category_id=product_item.category_id,
                is_perishable=product_item.is_perishable,
                shelf_life_days=product_item.shelf_life_days
            )
            db.session.add(reserved_item)
            db.session.flush()
        
        return reserved_item
    
    @staticmethod
    def get_product_item_for_reserved(reserved_item_id):
        """Get the original product item from a reserved item"""
        reserved_item = InventoryItem.query.get(reserved_item_id)
        if not reserved_item or reserved_item.type != 'product-reserved':
            return None
        
        original_name = reserved_item.name.replace(" (Reserved)", "")
        product_item = InventoryItem.query.filter_by(
            name=original_name,
            type='product',
            organization_id=reserved_item.organization_id
        ).first()
        
        return product_item
    
    @staticmethod
    def get_total_inventory_for_sku(sku):
        """Get combined available + reserved quantities for a SKU"""
        if not sku.inventory_item:
            return 0.0
        
        # Get available quantity
        available_qty = sku.inventory_item.quantity
        
        # Get reserved quantity
        reserved_item = ReservationService.get_reserved_item_for_product(sku.inventory_item.id)
        reserved_qty = reserved_item.quantity if reserved_item else 0.0
        
        return available_qty + reserved_qty
    
    @staticmethod
    def get_reservation_summary_for_sku(sku):
        """Get reservation summary for display in SKU view"""
        if not sku.inventory_item:
            return {
                'available': 0.0,
                'reserved': 0.0,
                'total': 0.0,
                'reservations': []
            }
        
        available_qty = sku.inventory_item.quantity
        reserved_item = ReservationService.get_reserved_item_for_product(sku.inventory_item.id)
        reserved_qty = reserved_item.quantity if reserved_item else 0.0
        
        # Get active reservations by order
        reservations = []
        if reserved_item:
            reservation_entries = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == reserved_item.id,
                    InventoryHistory.change_type == 'reserved_allocation',
                    InventoryHistory.remaining_quantity > 0,
                    InventoryHistory.order_id.isnot(None)
                )
            ).all()
            
            # Group by order_id
            order_reservations = {}
            for entry in reservation_entries:
                order_id = entry.order_id
                if order_id not in order_reservations:
                    order_reservations[order_id] = {
                        'order_id': order_id,
                        'quantity': 0.0,
                        'created_at': entry.timestamp
                    }
                order_reservations[order_id]['quantity'] += entry.remaining_quantity
            
            reservations = list(order_reservations.values())
        
        return {
            'available': available_qty,
            'reserved': reserved_qty,
            'total': available_qty + reserved_qty,
            'reservations': reservations
        }
