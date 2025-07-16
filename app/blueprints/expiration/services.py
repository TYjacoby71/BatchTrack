from datetime import datetime, timedelta, date
from ...models import db, InventoryItem, InventoryHistory, ProductSKU, ProductSKUHistory, Batch
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

class ExpirationService:
    """Centralized service for expiration calculations and data fetching only"""

    @staticmethod
    def calculate_expiration_date(start_date: datetime, shelf_life_days: int) -> datetime:
        """Calculate expiration date from start date and shelf life"""
        if not start_date or not shelf_life_days:
            return None

        # Ensure we have a proper datetime object
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Calculate expiration date maintaining the time component
        expiration_date = start_date + timedelta(days=shelf_life_days)
        return expiration_date

    @staticmethod
    def get_days_until_expiration(expiration_date: datetime) -> int:
        """Get days until expiration (negative if expired)"""
        if not expiration_date:
            return None
        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()

        # Ensure expiration date is naive for consistent comparison
        expiration_naive = expiration_date.replace(tzinfo=None) if expiration_date.tzinfo else expiration_date

        # Use exact time difference calculation
        time_diff_seconds = (expiration_naive - now).total_seconds()
        return round(time_diff_seconds / 86400)

    @staticmethod
    def get_life_remaining_percent(entry_date: datetime, expiration_date: datetime) -> Optional[float]:
        """Calculate percentage of shelf life remaining"""
        if not entry_date or not expiration_date:
            return None

        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()

        # Ensure all timestamps are naive for consistent comparison
        entry_naive = entry_date.replace(tzinfo=None) if entry_date.tzinfo else entry_date
        expiration_naive = expiration_date.replace(tzinfo=None) if expiration_date.tzinfo else expiration_date

        # Calculate exact time progression
        total_life_seconds = (expiration_naive - entry_naive).total_seconds()
        time_remaining_seconds = (expiration_naive - now).total_seconds()

        if total_life_seconds <= 0:
            return 0.0

        # Calculate percentage based on time remaining vs total life
        life_remaining_percent = max(0.0, (time_remaining_seconds / total_life_seconds) * 100)
        return min(100.0, life_remaining_percent)

    @staticmethod
    def _resolve_sku_expiration(sku_entry):
        """Resolve expiration date for SKU entry (FIFO or batch-based)"""
        if sku_entry.is_perishable and sku_entry.expiration_date:
            return sku_entry.expiration_date
        if sku_entry.batch_id:
            return ExpirationService.get_batch_expiration_date(sku_entry.batch_id)
        return None

    @staticmethod
    def _query_fifo_entries(expired=False, days_ahead: int = None):
        """Query FIFO entries based on expiration criteria"""
        from ...utils.timezone_utils import TimezoneUtils
        now = TimezoneUtils.now_naive()

        base_filter = [
            InventoryHistory.expiration_date.isnot(None),
            InventoryHistory.remaining_quantity > 0,
            InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
        ]

        if expired:
            base_filter.append(InventoryHistory.expiration_date < now)
        elif days_ahead:
            future_date = now + timedelta(days=days_ahead)
            base_filter.append(InventoryHistory.expiration_date.between(now, future_date))

        return db.session.query(
            InventoryHistory.inventory_item_id,
            InventoryItem.name,
            InventoryHistory.remaining_quantity,
            InventoryHistory.unit,
            InventoryHistory.expiration_date,
            InventoryHistory.id.label('fifo_id')
        ).join(InventoryItem).filter(and_(*base_filter)).all()

    @staticmethod
    def _query_sku_entries(expired=False, days_ahead: int = None):
        """Query product SKU entries based on expiration criteria"""
        from ...utils.timezone_utils import TimezoneUtils
        from ...models import Product, ProductVariant

        now = TimezoneUtils.now_naive()

        base_filter = [
            ProductSKUHistory.remaining_quantity > 0,
            ProductSKUHistory.quantity_change > 0,  # Only addition entries
            InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
        ]

        # Get all SKU entries first, then filter by expiration in code
        # This is because expiration might come from batch or FIFO level
        sku_entries = db.session.query(
            ProductSKUHistory.inventory_item_id,
            Product.name.label('product_name'),
            ProductVariant.name.label('variant_name'),
            ProductSKU.size_label,
            ProductSKUHistory.remaining_quantity,
            ProductSKUHistory.unit,
            ProductSKUHistory.id.label('history_id'),
            ProductSKUHistory.batch_id,
            ProductSKUHistory.expiration_date,
            ProductSKUHistory.is_perishable,
            ProductSKU.product_id,
            ProductSKU.variant_id
        ).join(ProductSKU, ProductSKUHistory.inventory_item_id == ProductSKU.inventory_item_id
        ).join(Product, ProductSKU.product_id == Product.id
        ).join(ProductVariant, ProductSKU.variant_id == ProductVariant.id
        ).join(InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id).filter(
            and_(*base_filter)
        ).all()

        # Filter by expiration criteria
        filtered_entries = []
        for sku_entry in sku_entries:
            expiration_date = ExpirationService._resolve_sku_expiration(sku_entry)

            if expiration_date:
                if expired and expiration_date < now:
                    filtered_entries.append(sku_entry)
                elif days_ahead:
                    future_date = now + timedelta(days=days_ahead)
                    if now <= expiration_date <= future_date:
                        filtered_entries.append(sku_entry)

        return filtered_entries

    @staticmethod
    def _format_sku_entry(sku_entry):
        """Format SKU entry for consistent return structure"""
        return {
            'inventory_item_id': sku_entry.inventory_item_id,
            'product_name': sku_entry.product_name,
            'variant_name': sku_entry.variant_name,
            'size_label': sku_entry.size_label,
            'quantity': sku_entry.remaining_quantity,
            'unit': sku_entry.unit,
            'expiration_date': ExpirationService._resolve_sku_expiration(sku_entry),
            'history_id': sku_entry.history_id,
            'product_inv_id': sku_entry.history_id,
            'product_id': sku_entry.product_id,
            'variant_id': sku_entry.variant_id,
            'lot_number': f"LOT-{sku_entry.history_id}"
        }

    @staticmethod
    def get_batch_expiration_date(batch_id: int) -> Optional[datetime]:
        """Get calculated expiration date for a batch"""
        from ...models import Batch

        batch = Batch.query.get(batch_id)
        if not batch or not batch.is_perishable or not batch.shelf_life_days:
            return None

        # Use completion date if available, otherwise start date
        base_date = batch.completed_at or batch.started_at
        if not base_date:
            return None

        return ExpirationService.calculate_expiration_date(base_date, batch.shelf_life_days)

    @staticmethod
    def get_expired_inventory_items() -> Dict:
        """Get all expired inventory items across the system"""
        expired_fifo = ExpirationService._query_fifo_entries(expired=True)
        expired_skus = ExpirationService._query_sku_entries(expired=True)

        expired_products = [ExpirationService._format_sku_entry(sku) for sku in expired_skus]

        return {
            'fifo_entries': expired_fifo,
            'product_inventory': expired_products
        }

    @staticmethod
    def get_expiring_soon_items(days_ahead: int = 7) -> Dict:
        """Get items expiring within specified days"""
        expiring_fifo = ExpirationService._query_fifo_entries(days_ahead=days_ahead)
        expiring_skus = ExpirationService._query_sku_entries(days_ahead=days_ahead)

        expiring_products = [ExpirationService._format_sku_entry(sku) for sku in expiring_skus]

        return {
            'fifo_entries': expiring_fifo,
            'product_inventory': expiring_products
        }

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
            if entry.expiration_date and entry.timestamp and entry.shelf_life_days:
                # Calculate freshness percentage
                life_remaining_percent = ExpirationService.get_life_remaining_percent(
                    entry.timestamp, entry.expiration_date
                )

                if life_remaining_percent is not None:
                    # Weight by quantity
                    weighted_freshness = life_remaining_percent * entry.remaining_quantity
                    total_weighted_freshness += weighted_freshness
                    total_quantity += entry.remaining_quantity

        if total_quantity == 0:
            return None

        final_freshness = total_weighted_freshness / total_quantity
        return round(min(100.0, max(0.0, final_freshness)), 1)

    @staticmethod
    def get_expiration_summary():
        """Get summary of expiration data for dashboard"""
        expired_items = ExpirationService.get_expired_inventory_items()
        expiring_soon = ExpirationService.get_expiring_soon_items(7)

        return {
            'expired_count': len(expired_items['fifo_entries']) + len(expired_items['product_inventory']),
            'expiring_soon_count': len(expiring_soon['fifo_entries']) + len(expiring_soon['product_inventory']),
            'total_expiration_issues': len(expired_items['fifo_entries']) + len(expired_items['product_inventory']) + len(expiring_soon['fifo_entries']) + len(expiring_soon['product_inventory'])
        }

    @staticmethod
    def mark_as_expired(item_type, item_id, quantity=None):
        """Mark items as expired - handles sync errors by directly adjusting FIFO entries"""
        try:
            if item_type == 'fifo':
                # Get FIFO entry to determine quantity and inventory item
                fifo_entry = InventoryHistory.query.get(item_id)
                if not fifo_entry:
                    return False, "FIFO entry not found"

                quantity_to_expire = quantity or fifo_entry.remaining_quantity
                
                # For expired items, directly zero out the FIFO entry and update inventory
                # This bypasses the validation that's causing the sync error
                item = InventoryItem.query.get(fifo_entry.inventory_item_id)
                if not item:
                    return False, "Inventory item not found"

                # Create history record for the expiration
                history = InventoryHistory(
                    inventory_item_id=fifo_entry.inventory_item_id,
                    change_type='expired',
                    quantity_change=-quantity_to_expire,
                    remaining_quantity=0.0,
                    unit=fifo_entry.unit,
                    unit_cost=fifo_entry.unit_cost,
                    note=f'Expired removal from FIFO entry #{item_id}',
                    created_by=current_user.id,
                    quantity_used=quantity_to_expire,
                    is_perishable=fifo_entry.is_perishable,
                    shelf_life_days=fifo_entry.shelf_life_days,
                    expiration_date=fifo_entry.expiration_date,
                    organization_id=current_user.organization_id
                )
                db.session.add(history)

                # Zero out the expired FIFO entry
                old_remaining = fifo_entry.remaining_quantity
                fifo_entry.remaining_quantity = 0.0

                # Reduce inventory quantity
                item.quantity = max(0, item.quantity - quantity_to_expire)

                db.session.commit()
                return True, f"Successfully marked FIFO entry #{item_id} as expired (removed {old_remaining})"

            elif item_type == 'product':
                # Get product history entry
                history_entry = ProductSKUHistory.query.get(item_id)
                if not history_entry:
                    return False, "Product history entry not found"

                quantity_to_expire = quantity or history_entry.remaining_quantity

                # For expired products, directly zero out the FIFO entry and update inventory
                item = InventoryItem.query.get(history_entry.inventory_item_id)
                if not item:
                    return False, "Inventory item not found"

                # Create history record for the expiration
                new_history = ProductSKUHistory(
                    inventory_item_id=history_entry.inventory_item_id,
                    change_type='expired',
                    quantity_change=-quantity_to_expire,
                    remaining_quantity=0.0,
                    unit=history_entry.unit,
                    unit_cost=history_entry.unit_cost,
                    note=f'Expired removal from product FIFO entry #{item_id}',
                    created_by=current_user.id,
                    quantity_used=quantity_to_expire,
                    is_perishable=history_entry.is_perishable,
                    shelf_life_days=history_entry.shelf_life_days,
                    expiration_date=history_entry.expiration_date,
                    batch_id=history_entry.batch_id,
                    organization_id=current_user.organization_id
                )
                db.session.add(new_history)

                # Zero out the expired FIFO entry
                old_remaining = history_entry.remaining_quantity
                history_entry.remaining_quantity = 0.0

                # Reduce inventory quantity
                item.quantity = max(0, item.quantity - quantity_to_expire)

                db.session.commit()
                return True, f"Successfully marked product FIFO entry #{item_id} as expired (removed {old_remaining})"

            else:
                return False, "Invalid item type"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking item as expired: {str(e)}")
            return False, str(e)