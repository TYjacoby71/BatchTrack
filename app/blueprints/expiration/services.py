from datetime import datetime, timedelta, date
from ...models import db, InventoryItem, InventoryHistory, ProductSKU, ProductSKUHistory, Batch
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import and_
from ...models import db, InventoryHistory, InventoryItem, ProductInventory, Batch

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from ...models import db, InventoryItem, InventoryHistory, ProductInventory, Batch
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
    def get_batch_expiration_date(batch_id: int) -> Optional[datetime]:
        """Get calculated expiration date for a batch"""
        from models import Batch

        batch = Batch.query.get(batch_id)
        if not batch or not batch.is_perishable or not batch.shelf_life_days:
            return None

        # Use completion date if available, otherwise start date
        base_date = batch.completed_at or batch.started_at
        if not base_date:
            return None

        return ExpirationService.calculate_expiration_date(base_date, batch.shelf_life_days)

    @staticmethod
    def get_product_inventory_expiration_date(product_inventory_id: int) -> Optional[datetime]:
        """Get expiration date for product inventory, preferring batch calculation"""
        from models import ProductInventory

        inventory = ProductInventory.query.get(product_inventory_id)
        if not inventory:
            return None

        # First try batch-based calculation
        if inventory.batch_id:
            batch_expiration = ExpirationService.get_batch_expiration_date(inventory.batch_id)
            if batch_expiration:
                return batch_expiration

        # Fallback to stored expiration date
        return inventory.expiration_date

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

        # Get expired product inventory with batch-aware calculation
        product_inventories = db.session.query(ProductInventory).filter(
            ProductInventory.quantity > 0
        ).all()

        expired_products = []
        for inv in product_inventories:
            expiration_date = ExpirationService.get_product_inventory_expiration_date(inv.id)
            if expiration_date and expiration_date.date() < today:
                expired_products.append({
                    'product_id': inv.product_id,
                    'variant': inv.variant,
                    'size_label': inv.size_label,
                    'quantity': inv.quantity,
                    'unit': inv.unit,
                    'expiration_date': expiration_date,
                    'product_inv_id': inv.id
                })

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

        # Product inventory expiring soon with batch-aware calculation
        product_inventories = db.session.query(ProductInventory).filter(
            ProductInventory.quantity > 0
        ).all()

        expiring_products = []
        for inv in product_inventories:
            expiration_date = ExpirationService.get_product_inventory_expiration_date(inv.id)
            if expiration_date and today <= expiration_date.date() <= future_date:
                expiring_products.append({
                    'product_id': inv.product_id,
                    'variant': inv.variant,
                    'size_label': inv.size_label,
                    'quantity': inv.quantity,
                    'unit': inv.unit,
                    'expiration_date': expiration_date,
                    'product_inv_id': inv.id
                })

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
    def get_expiration_summary():
        """Get summary counts for dashboard integration"""
        today = datetime.now().date()
        future_date = today + timedelta(days=7)

        # Count expired items with remaining quantity
        expired_fifo_count = InventoryHistory.query.filter(
            and_(
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today,
                InventoryHistory.remaining_quantity > 0
            )
        ).count()

        expired_products_count = ProductInventory.query.filter(
            and_(
                ProductInventory.expiration_date != None,
                ProductInventory.expiration_date < today,
                ProductInventory.quantity > 0
            )
        ).count()

        # Count items expiring soon
        expiring_fifo_count = InventoryHistory.query.filter(
            and_(
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date.between(today, future_date),
                InventoryHistory.remaining_quantity > 0
            )
        ).count()

        expiring_products_count = ProductInventory.query.filter(
            and_(
                ProductInventory.expiration_date != None,
                ProductInventory.expiration_date.between(today, future_date),
                ProductInventory.quantity > 0
            )
        ).count()

        return {
            'expired_total': expired_fifo_count + expired_products_count,
            'expired_fifo': expired_fifo_count,
            'expired_products': expired_products_count,
            'expiring_soon_total': expiring_fifo_count + expiring_products_count,
            'expiring_soon_fifo': expiring_fifo_count,
            'expiring_soon_products': expiring_products_count
        }

    @staticmethod
    def get_inventory_item_expiration_status(inventory_item_id: int):
        """Get expiration status for a specific inventory item"""
        today = datetime.now().date()
        future_date = today + timedelta(days=7)

        # Get all FIFO entries for this item
        entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None
            )
        ).all()

        expired_entries = []
        expiring_soon_entries = []

        for entry in entries:
            if entry.expiration_date < today:
                expired_entries.append(entry)
            elif entry.expiration_date <= future_date:
                expiring_soon_entries.append(entry)

        return {
            'expired_entries': expired_entries,
            'expiring_soon_entries': expiring_soon_entries,
            'has_expiration_issues': len(expired_entries) > 0 or len(expiring_soon_entries) > 0
        }

    @staticmethod
    def get_product_expiration_status(product_id: int):
        """Get expiration status for a specific product"""
        today = datetime.now().date()
        future_date = today + timedelta(days=7)

        # Get all product inventory for this product
        inventory = ProductInventory.query.filter(
            and_(
                ProductInventory.product_id == product_id,
                ProductInventory.quantity > 0,
                ProductInventory.expiration_date != None
            )
        ).all()

        expired_inventory = []
        expiring_soon_inventory = []

        for item in inventory:
            if item.expiration_date < today:
                expired_inventory.append(item)
            elif item.expiration_date <= future_date:
                expiring_soon_inventory.append(item)

        return {
            'expired_inventory': expired_inventory,
            'expiring_soon_inventory': expiring_soon_inventory,
            'has_expiration_issues': len(expired_inventory) > 0 or len(expiring_soon_inventory) > 0
        }

    @staticmethod
    def mark_as_spoiled(item_type: str, item_id: int):
        """Mark an expired item as spoiled and remove from inventory"""
        from flask_login import current_user

        if item_type == 'fifo':
            # Handle FIFO entry spoilage
            entry = InventoryHistory.query.get(item_id)
            if not entry or entry.remaining_quantity <= 0:
                raise ValueError("FIFO entry not found or has no remaining quantity")

            # Use centralized inventory adjustment service
            from services.inventory_adjustment import process_inventory_adjustment

            success = process_inventory_adjustment(
                item_id=entry.inventory_item_id,
                quantity=entry.remaining_quantity,
                change_type='spoil',
                unit=entry.unit,
                notes=f"Marked as spoiled - expired on {entry.expiration_date}",
                created_by=current_user.id if current_user.is_authenticated else None
            )

            return 1 if success else 0

        elif item_type == 'product':
            # Handle product inventory spoilage
            product_item = ProductInventory.query.get(item_id)
            if not product_item or product_item.quantity <= 0:
                raise ValueError("Product item not found or has no remaining quantity")

            # Use centralized product adjustment service
            from services.product_adjustment_service import ProductAdjustmentService

            success = ProductAdjustmentService.adjust_product_inventory(
                product_inventory_id=product_item.id,
                quantity_change=-product_item.quantity,
                adjustment_type='spoil',
                notes=f"Marked as spoiled - expired on {product_item.expiration_date}",
                created_by=current_user.id if current_user.is_authenticated else None
            )

            return 1 if success else 0

        else:
            raise ValueError("Invalid item type. Must be 'fifo' or 'product'")

        return 0