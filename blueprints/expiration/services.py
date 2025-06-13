
from datetime import datetime, timedelta, date
from models import db, InventoryItem, InventoryHistory, ProductInventory, ProductInventoryHistory, Batch
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import and_
from models import db, InventoryHistory, InventoryItem, ProductInventory, Batch

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import db, InventoryItem, InventoryHistory, ProductInventory, Batch
from sqlalchemy import and_

class ExpirationService:
    """Centralized service for all expiration-related operations"""
    
    @staticmethod
    def calculate_expiration_date(entry_date: datetime, shelf_life_days: int) -> datetime:
        """Calculate expiration date from entry date and shelf life"""
        if not entry_date or not shelf_life_days:
            return None
        return entry_date + timedelta(days=shelf_life_days)
    
    @staticmethod
    def get_days_until_expiration(expiration_date: datetime) -> int:
        """Get days until expiration (negative if expired)"""
        if not expiration_date:
            return None
        today = datetime.now().date()
        exp_date = expiration_date.date() if isinstance(expiration_date, datetime) else expiration_date
        return (exp_date - today).days
    
    @staticmethod
    def get_life_remaining_percent(entry_date: datetime, expiration_date: datetime) -> Optional[float]:
        """Calculate percentage of shelf life remaining"""
        if not entry_date or not expiration_date:
            return None
        
        now = datetime.now()
        total_life = (expiration_date - entry_date).total_seconds()
        if total_life <= 0:
            return 0.0
        
        time_passed = (now - entry_date).total_seconds()
        remaining = max(0, total_life - time_passed)
        return (remaining / total_life) * 100
    
    @staticmethod
    def update_fifo_expiration_data(inventory_item_id: int, shelf_life_days: int):
        """Update expiration data for all FIFO entries with remaining quantity"""
        entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).all()

        for entry in entries:
            entry.is_perishable = True
            entry.shelf_life_days = shelf_life_days
            if entry.timestamp:
                entry.expiration_date = ExpirationService.calculate_expiration_date(
                    entry.timestamp, shelf_life_days
                )
        
        db.session.commit()
    
    @staticmethod
    def get_expired_inventory_items() -> List[Dict]:
        """Get all expired inventory items across the system"""
        today = datetime.now().date()
        
        # Get expired FIFO entries
        expired_fifo = db.session.query(
            InventoryHistory.inventory_item_id,
            InventoryItem.name,
            InventoryHistory.remaining_quantity,
            InventoryHistory.unit,
            InventoryHistory.expiration_date,
            InventoryHistory.id.label('fifo_id')
        ).join(InventoryItem).filter(
            and_(
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today,
                InventoryHistory.remaining_quantity > 0
            )
        ).all()
        
        # Get expired product inventory
        expired_products = db.session.query(
            ProductInventory.product_id,
            ProductInventory.variant,
            ProductInventory.size_label,
            ProductInventory.quantity,
            ProductInventory.unit,
            ProductInventory.expiration_date,
            ProductInventory.id.label('product_inv_id')
        ).filter(
            and_(
                ProductInventory.expiration_date != None,
                ProductInventory.expiration_date < today,
                ProductInventory.quantity > 0
            )
        ).all()
        
        return {
            'fifo_entries': expired_fifo,
            'product_inventory': expired_products
        }
    
    @staticmethod
    def get_expiring_soon_items(days_ahead: int = 7) -> List[Dict]:
        """Get items expiring within specified days"""
        future_date = datetime.now().date() + timedelta(days=days_ahead)
        today = datetime.now().date()
        
        # FIFO entries expiring soon
        expiring_fifo = db.session.query(
            InventoryHistory.inventory_item_id,
            InventoryItem.name,
            InventoryHistory.remaining_quantity,
            InventoryHistory.unit,
            InventoryHistory.expiration_date,
            InventoryHistory.id.label('fifo_id')
        ).join(InventoryItem).filter(
            and_(
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date.between(today, future_date),
                InventoryHistory.remaining_quantity > 0
            )
        ).all()
        
        # Product inventory expiring soon
        expiring_products = db.session.query(
            ProductInventory.product_id,
            ProductInventory.variant,
            ProductInventory.size_label,
            ProductInventory.quantity,
            ProductInventory.unit,
            ProductInventory.expiration_date,
            ProductInventory.id.label('product_inv_id')
        ).filter(
            and_(
                ProductInventory.expiration_date != None,
                ProductInventory.expiration_date.between(today, future_date),
                ProductInventory.quantity > 0
            )
        ).all()
        
        return {
            'fifo_entries': expiring_fifo,
            'product_inventory': expiring_products
        }
    
    @staticmethod
    def set_batch_expiration(batch_id: int, is_perishable: bool, shelf_life_days: Optional[int] = None):
        """Set expiration data for a batch"""
        batch = Batch.query.get(batch_id)
        if not batch:
            return False
        
        batch.is_perishable = is_perishable
        batch.shelf_life_days = shelf_life_days
        
        if is_perishable and shelf_life_days:
            batch.expiration_date = ExpirationService.calculate_expiration_date(
                batch.started_at, shelf_life_days
            )
        else:
            batch.expiration_date = None
        
        db.session.commit()
        return True
    
    @staticmethod
    def archive_expired_items():
        """Archive expired items with zero quantity"""
        today = datetime.now().date()
        
        # Archive expired FIFO entries with no remaining quantity
        expired_fifo = InventoryHistory.query.filter(
            and_(
                InventoryHistory.expiration_date < today,
                InventoryHistory.remaining_quantity <= 0
            )
        ).all()
        
        for entry in expired_fifo:
            db.session.delete(entry)
        
        # Archive expired product inventory with zero quantity
        expired_products = ProductInventory.query.filter(
            and_(
                ProductInventory.expiration_date < today,
                ProductInventory.quantity <= 0
            )
        ).all()
        
        for item in expired_products:
            db.session.delete(item)
        
        db.session.commit()
        return len(expired_fifo) + len(expired_products)
    
    @staticmethod
    def mark_as_spoiled(item_type: str, item_id: int):
        """Mark an expired item as spoiled and remove from inventory"""
        from flask_login import current_user
        
        if item_type == 'fifo':
            # Handle FIFO entry spoilage
            entry = InventoryHistory.query.get(item_id)
            if not entry or entry.remaining_quantity <= 0:
                raise ValueError("FIFO entry not found or has no remaining quantity")
            
            # Create spoilage record
            spoilage_record = InventoryHistory(
                inventory_item_id=entry.inventory_item_id,
                change_type='spoilage',
                quantity_change=-entry.remaining_quantity,
                unit=entry.unit,
                remaining_quantity=0,
                fifo_reference_id=entry.id,
                note=f"Marked as spoiled - expired on {entry.expiration_date}",
                created_by=current_user.id if current_user.is_authenticated else None,
                quantity_used=entry.remaining_quantity,
                timestamp=datetime.utcnow()
            )
            
            # Zero out the original entry
            entry.remaining_quantity = 0
            
            db.session.add(spoilage_record)
            db.session.commit()
            return 1
            
        elif item_type == 'product':
            # Handle product inventory spoilage
            product_item = ProductInventory.query.get(item_id)
            if not product_item or product_item.quantity <= 0:
                raise ValueError("Product item not found or has no remaining quantity")
            
            # Create spoilage record in ProductInventoryHistory
            from models import ProductInventoryHistory
            spoilage_record = ProductInventoryHistory(
                product_inventory_id=product_item.id,
                product_id=product_item.product_id,
                change_type='spoilage',
                quantity_change=-product_item.quantity,
                unit=product_item.unit,
                note=f"Marked as spoiled - expired on {product_item.expiration_date}",
                created_by=current_user.id if current_user.is_authenticated else None,
                timestamp=datetime.utcnow()
            )
            
            # Zero out the product inventory
            product_item.quantity = 0
            
            db.session.add(spoilage_record)
            db.session.commit()
            return 1
        
        else:
            raise ValueError("Invalid item type. Must be 'fifo' or 'product'")
        
        return 0
