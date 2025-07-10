from datetime import datetime, timedelta, date
from ...models import db, InventoryItem, InventoryHistory, ProductSKU, ProductSKUHistory, Batch
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple

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
        # This method is deprecated - use get_sku_expiration_date instead
        return None

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

        # Get expired product SKUs with batch-aware calculation
        from ...models import ProductSKU, ProductSKUHistory, Product, ProductVariant

        # Get SKUs with remaining quantity from FIFO entries
        expired_skus = db.session.query(
            ProductSKUHistory.inventory_item_id,
            Product.name.label('product_name'),
            ProductVariant.name.label('variant_name'),
            ProductSKU.size_label,
            ProductSKUHistory.remaining_quantity,
            ProductSKUHistory.unit,
            ProductSKUHistory.id.label('history_id'),
            ProductSKUHistory.batch_id
        ).join(ProductSKU, ProductSKUHistory.inventory_item_id == ProductSKU.inventory_item_id
        ).join(Product, ProductSKU.product_id == Product.id
        ).join(ProductVariant, ProductSKU.variant_id == ProductVariant.id).filter(
            and_(
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.quantity_change > 0  # Only addition entries
            )
        ).all()

        expired_products = []
        for sku_entry in expired_skus:
            # Check if this SKU entry is from an expired batch
            if sku_entry.batch_id:
                batch_expiration = ExpirationService.get_batch_expiration_date(sku_entry.batch_id)
                if batch_expiration and batch_expiration.date() < today:
                    expired_products.append({
                        'inventory_item_id': sku_entry.inventory_item_id,
                        'product_name': sku_entry.product_name,
                        'variant_name': sku_entry.variant_name,
                        'size_label': sku_entry.size_label,
                        'quantity': sku_entry.remaining_quantity,
                        'unit': sku_entry.unit,
                        'expiration_date': batch_expiration,
                        'history_id': sku_entry.history_id
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

        # Product SKUs expiring soon with batch-aware calculation
        from ...models import ProductSKU, ProductSKUHistory, Product, ProductVariant

        # Get SKUs with remaining quantity from FIFO entries
        expiring_skus = db.session.query(
            ProductSKUHistory.inventory_item_id,
            Product.name.label('product_name'),
            ProductVariant.name.label('variant_name'),
            ProductSKU.size_label,
            ProductSKUHistory.remaining_quantity,
            ProductSKUHistory.unit,
            ProductSKUHistory.id.label('history_id'),
            ProductSKUHistory.batch_id
        ).join(ProductSKU, ProductSKUHistory.inventory_item_id == ProductSKU.inventory_item_id
        ).join(Product, ProductSKU.product_id == Product.id
        ).join(ProductVariant, ProductSKU.variant_id == ProductVariant.id).filter(
            and_(
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.quantity_change > 0  # Only addition entries
            )
        ).all()

        expiring_products = []
        for sku_entry in expiring_skus:
            # Check if this SKU entry is from a batch expiring soon
            if sku_entry.batch_id:
                batch_expiration = ExpirationService.get_batch_expiration_date(sku_entry.batch_id)
                if batch_expiration and today <= batch_expiration.date() <= future_date:
                    expiring_products.append({
                        'inventory_item_id': sku_entry.inventory_item_id,
                        'product_name': sku_entry.product_name,
                        'variant_name': sku_entry.variant_name,
                        'size_label': sku_entry.size_label,
                        'quantity': sku_entry.remaining_quantity,
                        'unit': sku_entry.unit,
                        'expiration_date': batch_expiration,
                        'history_id': sku_entry.history_id
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

        # Archive expired product SKU history entries with zero remaining
        expired_sku_history = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.remaining_quantity <= 0,
                ProductSKUHistory.quantity_change > 0
            )
        ).all()

        for item in expired_sku_history:
            # Don't delete history entries, just mark them as archived if needed
            pass

        db.session.commit()
        return len(expired_fifo) + len(expired_sku_history)

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

        # For now, set product counts to 0 since we need to implement batch-based expiration
        expired_products_count = 0

        # Count items expiring soon
        expiring_fifo_count = InventoryHistory.query.filter(
            and_(
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date.between(today, future_date),
                InventoryHistory.remaining_quantity > 0
            )
        ).count()

        # For now, set product counts to 0 since we need to implement batch-based expiration
        expiring_products_count = 0

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
    def get_weighted_average_freshness(inventory_item_id: int) -> Optional[float]:
        """Calculate weighted average freshness for an inventory item based on FIFO entries"""
        # Get all FIFO entries with remaining quantity
        entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.is_perishable == True,
                InventoryHistory.expiration_date != None
            )
        ).all()

        if not entries:
            return None

        total_weighted_freshness = 0.0
        total_quantity = 0.0
        now = datetime.now()

        for entry in entries:
            if entry.timestamp and entry.expiration_date:
                # Calculate life remaining percentage based on timestamps
                total_life_seconds = (entry.expiration_date - entry.timestamp).total_seconds()
                if total_life_seconds <= 0:
                    life_remaining_percent = 0.0
                else:
                    time_passed_seconds = (now - entry.timestamp).total_seconds()
                    remaining_seconds = max(0, total_life_seconds - time_passed_seconds)
                    life_remaining_percent = (remaining_seconds / total_life_seconds) * 100

                # Weight by quantity
                weighted_freshness = life_remaining_percent * entry.remaining_quantity
                total_weighted_freshness += weighted_freshness
                total_quantity += entry.remaining_quantity

        if total_quantity == 0:
            return None

        return round(total_weighted_freshness / total_quantity, 1)

    @staticmethod
    def get_product_expiration_status(product_id: int):
        """Get expiration status for a specific product"""
        # For now, return empty status since we need to implement batch-based expiration
        return {
            'expired_inventory': [],
            'expiring_soon_inventory': [],
            'has_expiration_issues': False
        }

    @staticmethod
    def mark_as_spoiled(item_type: str, item_id: int):
        """Mark an expired item as spoiled and remove from inventory"""
        from flask_login import current_user

        # Convert item_id to int to ensure proper type
        try:
            item_id = int(item_id)
        except (ValueError, TypeError):
            raise ValueError("Invalid item ID")

        if item_type == 'fifo':
            # Handle FIFO entry spoilage
            entry = InventoryHistory.query.get(item_id)
            if not entry or float(entry.remaining_quantity) <= 0:
                raise ValueError("FIFO entry not found or has no remaining quantity")

            # Use centralized inventory adjustment service
            from ...services.inventory_adjustment import process_inventory_adjustment

            success = process_inventory_adjustment(
                item_id=entry.inventory_item_id,
                quantity=float(entry.remaining_quantity),
                change_type='spoil',
                unit=entry.unit,
                notes=f"Marked as spoiled - expired on {entry.expiration_date}",
                created_by=current_user.id if current_user.is_authenticated else None
            )

            return 1 if success else 0

        elif item_type == 'product':
            # Handle product SKU history spoilage
            from ...services.product_inventory_service import ProductInventoryService

            history_entry = ProductSKUHistory.query.get(item_id)
            if not history_entry or float(history_entry.remaining_quantity) <= 0:
                raise ValueError("Product history entry not found or has no remaining quantity")

            # Use product inventory service to deduct the spoiled quantity
            success = ProductInventoryService.deduct_stock(
                inventory_item_id=history_entry.inventory_item_id,
                quantity=float(history_entry.remaining_quantity),
                change_type='spoil',
                notes=f"Marked as spoiled - expired batch"
            )

            return 1 if success else 0

        else:
            raise ValueError("Invalid item type. Must be 'fifo' or 'product'")

        return 0