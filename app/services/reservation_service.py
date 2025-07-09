
from flask import current_app
from flask_login import current_user
from ..models import db, InventoryItem, InventoryHistory, Reservation
from .inventory_adjustment import process_inventory_adjustment
from sqlalchemy import and_, func

class ReservationService:
    """Service for managing product reservations using new reservation model"""
    
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
        
        # Get available quantity (excludes expired)
        available_qty = sku.inventory_item.available_quantity
        
        # Get reserved quantity from active reservations
        reserved_qty = ReservationService.get_total_reserved_for_item(sku.inventory_item.id)
        
        return available_qty + reserved_qty
    
    @staticmethod
    def get_total_reserved_for_item(item_id):
        """Get total reserved quantity for a product from active reservations"""
        result = db.session.query(func.sum(Reservation.quantity)).filter(
            and_(
                Reservation.product_item_id == item_id,
                Reservation.status == 'active'
            )
        ).scalar()
        return result or 0.0
    
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
        
        available_qty = sku.inventory_item.available_quantity
        
        # Get active reservations grouped by order
        active_reservations = Reservation.query.filter(
            and_(
                Reservation.product_item_id == sku.inventory_item.id,
                Reservation.status == 'active'
            )
        ).all()
        
        # Group by order_id for display
        order_reservations = {}
        total_reserved = 0.0
        
        for reservation in active_reservations:
            order_id = reservation.order_id
            if order_id not in order_reservations:
                order_reservations[order_id] = {
                    'order_id': order_id,
                    'quantity': 0.0,
                    'created_at': reservation.created_at,
                    'expires_at': reservation.expires_at,
                    'source': reservation.source,
                    'sale_price': reservation.sale_price
                }
            order_reservations[order_id]['quantity'] += reservation.quantity
            total_reserved += reservation.quantity
        
        reservations = list(order_reservations.values())
        
        return {
            'available': available_qty,
            'reserved': total_reserved,
            'total': available_qty + total_reserved,
            'reservations': reservations
        }

    @staticmethod
    def get_reservation_details_for_order(order_id):
        """Get detailed reservation information for an order"""
        reservations = Reservation.query.filter_by(order_id=order_id).all()
        
        details = []
        for reservation in reservations:
            details.append({
                'id': reservation.id,
                'product_name': reservation.product_item.name if reservation.product_item else 'Unknown',
                'quantity': reservation.quantity,
                'unit': reservation.unit,
                'unit_cost': reservation.unit_cost,
                'sale_price': reservation.sale_price,
                'status': reservation.status,
                'created_at': reservation.created_at,
                'expires_at': reservation.expires_at,
                'source': reservation.source,
                'source_batch_id': reservation.source_batch_id
            })
        
        return details
