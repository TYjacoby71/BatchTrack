from datetime import datetime, timedelta, date
from ...models import db, InventoryItem, InventoryHistory, ProductSKU, ProductSKUHistory, Batch
from sqlalchemy import and_, or_, func
from typing import List, Dict, Optional, Tuple
from flask import current_app
from flask_login import current_user
from ...utils.timezone_utils import TimezoneUtils
import pytz

class ExpirationService:
    """Centralized service for all expiration-related operations"""

    @staticmethod
    def calculate_expiration_date(entry_date: datetime, shelf_life_days: int) -> datetime:
        """Calculate expiration date from entry date and shelf life"""
        if not entry_date or not shelf_life_days:
            return None
        # Preserve the exact timestamp to maintain precision
        return entry_date + timedelta(days=shelf_life_days)

    @staticmethod
    def get_days_until_expiration(expiration_date: datetime) -> int:
        """Get days until expiration (negative if expired)"""
        if not expiration_date:
            return None
        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.utc_now()  # Use consistent UTC time

        # Ensure both datetimes are timezone-aware or both are naive
        if expiration_date.tzinfo is None:
            # If expiration_date is naive, assume it's in UTC
            import pytz
            expiration_date = pytz.UTC.localize(expiration_date)

        if now.tzinfo is None:
            import pytz
            now = pytz.UTC.localize(now)

        time_diff = expiration_date - now
        return int(time_diff.total_seconds() / 86400)  # Convert seconds to days

    @staticmethod
    def get_life_remaining_percent(entry_date: datetime, expiration_date: datetime) -> Optional[float]:
        """Calculate percentage of shelf life remaining"""
        if not entry_date or not expiration_date:
            return None

        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()
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
    def get_expired_inventory_items():
        """Get all expired inventory items across different models"""
        from ...models import InventoryItem, ProductSKU
        from ...utils.timezone_utils import TimezoneUtils

        # Get current date in user's timezone
        today = TimezoneUtils.now_naive().date()

        expired_items = {
            'fifo_entries': [],
            'product_inventory': []
        }

        # Check expired FIFO entries from inventory history
        from ...models import InventoryHistory
        fifo_entries = InventoryHistory.query.filter(
            InventoryHistory.remaining_quantity > 0,
            InventoryHistory.expiration_date.isnot(None)
        ).all()

        for entry in fifo_entries:
            if entry.expiration_date:
                # Handle both date and datetime objects
                exp_date = entry.expiration_date.date() if hasattr(entry.expiration_date, 'date') else entry.expiration_date
                if exp_date < today:
                    # Ensure expiration_date is a date object for template compatibility
                    if hasattr(entry.expiration_date, 'date'):
                        entry.expiration_date = entry.expiration_date.date()
                    expired_items['fifo_entries'].append(entry)

        # Check product SKUs via their inventory items
        from ...models import InventoryItem
        product_skus = db.session.query(ProductSKU).join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            InventoryItem.quantity > 0,
            ProductSKU.expiration_date.isnot(None)
        ).all()

        for sku in product_skus:
            if sku.expiration_date:
                # Handle both date and datetime objects
                exp_date = sku.expiration_date.date() if hasattr(sku.expiration_date, 'date') else sku.expiration_date
                if exp_date < today:
                    # Ensure expiration_date is a date object for template compatibility
                    if hasattr(sku.expiration_date, 'date'):
                        sku.expiration_date = sku.expiration_date.date()
                    expired_items['product_inventory'].append(sku)

        return expired_items

    @staticmethod
    def get_expiring_soon_items(days_ahead=7):
        """Get items expiring within specified days"""
        from ...models import InventoryItem, ProductSKU
        from ...utils.timezone_utils import TimezoneUtils

        # Get current date and warning threshold in user's timezone
        today = TimezoneUtils.now_naive().date()
        warning_threshold = today + timedelta(days=days_ahead)

        expiring_items = {'fifo_entries': [], 'product_inventory': []}

        # Check FIFO entries from inventory history
        from ...models import InventoryHistory
        fifo_entries = InventoryHistory.query.filter(
            InventoryHistory.remaining_quantity > 0,
            InventoryHistory.expiration_date.isnot(None)
        ).all()

        for entry in fifo_entries:
            if entry.expiration_date:
                # Handle both date and datetime objects
                exp_date = entry.expiration_date.date() if hasattr(entry.expiration_date, 'date') else entry.expiration_date
                if today <= exp_date <= warning_threshold:
                    # Ensure expiration_date is a date object for template compatibility
                    if hasattr(entry.expiration_date, 'date'):
                        entry.expiration_date = entry.expiration_date.date()
                    expiring_items['fifo_entries'].append(entry)

        # Check product SKUs - get all SKUs with expiration dates and check their inventory
        all_product_skus = ProductSKU.query.filter(
            ProductSKU.expiration_date.isnot(None)
        ).all()

        for sku in all_product_skus:
            # Check if this SKU has quantity available
            if hasattr(sku, 'quantity') and sku.quantity > 0:
                exp_date = sku.expiration_date
                if isinstance(exp_date, str):
                    exp_date = datetime.strptime(exp_date, '%Y-%m-%d').date()
                elif hasattr(exp_date, 'date'):
                    exp_date = exp_date.date()

                if today <= exp_date <= warning_threshold:
                    # Ensure expiration_date is a date object for template compatibility
                    if hasattr(sku.expiration_date, 'date'):
                        sku.expiration_date = sku.expiration_date.date()
                    elif isinstance(sku.expiration_date, str):
                        sku.expiration_date = datetime.strptime(sku.expiration_date, '%Y-%m-%d').date()
                    expiring_items['product_inventory'].append(sku)

        return expiring_items

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
        from ...utils.timezone_utils import TimezoneUtils
        today = TimezoneUtils.now_naive().date()

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
    def is_item_expired(expiration_date: datetime) -> bool:
        """Check if an item is expired based on expiration date"""
        if not expiration_date:
            return False
        from ...utils.timezone_utils import TimezoneUtils
        today = TimezoneUtils.now_naive().date()
        exp_date = expiration_date.date() if isinstance(expiration_date, datetime) else expiration_date
        return exp_date < today

    @staticmethod
    def is_item_expiring_soon(expiration_date: datetime, days_ahead: int = 7) -> bool:
        """Check if an item is expiring within specified days"""
        if not expiration_date:
            return False
        from ...utils.timezone_utils import TimezoneUtils
        today = TimezoneUtils.now_naive().date()
        future_date = today + timedelta(days=days_ahead)
        exp_date = expiration_date.date() if isinstance(expiration_date, datetime) else expiration_date
        return today <= exp_date <= future_date

    @staticmethod
    def get_inventory_item_expiration_status(inventory_item_id: int):
        """Get expiration status for a specific inventory item"""
        from flask_login import current_user
        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()
        future_date = now + timedelta(days=7)

        # Get all FIFO entries for this item with organization scoping
        entries = db.session.query(InventoryHistory).join(InventoryItem).filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
            )
        ).all()

        expired_entries = []
        expiring_soon_entries = []

        for entry in entries:
            if entry.expiration_date < now:
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
        from flask_login import current_user

        # Get all FIFO entries with remaining quantity
        entries = db.session.query(InventoryHistory).join(InventoryItem).filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.is_perishable == True,
                InventoryHistory.expiration_date != None,
                InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
            )
        ).all()

        if not entries:
            return None

        total_weighted_freshness = 0.0
        total_quantity = 0.0
        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()

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

    @staticmethod
    def get_expiration_summary():
        """Get summary of expiration data for dashboard"""
        from flask_login import current_user

        expired_items = ExpirationService.get_expired_inventory_items()
        expiring_soon = ExpirationService.get_expiring_soon_items(7)

        return {
            'expired_count': len(expired_items['fifo_entries']) + len(expired_items['product_inventory']),
            'expiring_soon_count': len(expiring_soon['fifo_entries']) + len(expiring_soon['product_inventory']),
            'total_expiration_issues': len(expired_items['fifo_entries']) + len(expired_items['product_inventory']) + len(expiring_soon['fifo_entries']) + len(expiring_soon['product_inventory'])
        }

    @staticmethod
    def get_expiring_items(days_ahead=7, organization_id=None):
        """Get items expiring within the specified number of days"""
        if organization_id is None and current_user.is_authenticated:
            organization_id = current_user.organization_id

        if not organization_id:
            return []

        # Calculate cutoff date using user's timezone
        now = TimezoneUtils.now_naive()  # Get current time in user's timezone
        cutoff_date = now + timedelta(days=days_ahead)

        # Query for expiring items
        expiring_items = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.expiration_date <= cutoff_date
        ).all()

        return expiring_items

    @staticmethod
    def get_expired_items(organization_id=None):
        """Get items that have already expired"""
        if organization_id is None and current_user.is_authenticated:
            organization_id = current_user.organization_id

        if not organization_id:
            return []

        # Items expired as of today in user's timezone
        today = TimezoneUtils.now_naive().date()

        expired_items = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            func.date(InventoryItem.expiration_date) < today
        ).all()

        return expired_items

    @staticmethod
    def get_expiration_summary(organization_id=None):
        """Get a summary of expiring and expired items"""
        if organization_id is None and current_user.is_authenticated:
            organization_id = current_user.organization_id

        if not organization_id:
            return {
                'expiring_soon': 0,
                'expired': 0,
                'total_items': 0,
                'needs_attention': 0
            }

        today = TimezoneUtils.now_naive().date()

        expiring_soon = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.expiration_date >= today,
            InventoryItem.expiration_date <= (today + timedelta(days=7))
        ).count()

        expired = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            func.date(InventoryItem.expiration_date) < today
        ).count()

        total_items = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id
        ).count()

        needs_attention = expiring_soon + expired

        return {
            'expiring_soon': expiring_soon,
            'expired': expired,
            'total_items': total_items,
            'needs_attention': needs_attention
        }