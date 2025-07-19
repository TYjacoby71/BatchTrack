from datetime import datetime, timedelta, date, timezone
from ...models import db, InventoryItem, InventoryHistory, ProductSKU, ProductSKUHistory, Batch
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Tuple
from flask_login import current_user
import logging

# Set logger to INFO level to reduce debug noise
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ExpirationService:
    """Centralized service for expiration calculations and data fetching"""

    @staticmethod
    def calculate_expiration_date(start_date: datetime, shelf_life_days: int) -> datetime:
        """Calculate expiration date from start date and shelf life"""
        if not start_date or not shelf_life_days:
            return None

        # Ensure we have a proper datetime object
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Ensure start_date is timezone-aware (convert to UTC if naive)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        # Calculate expiration date maintaining the timezone
        expiration_date = start_date + timedelta(days=shelf_life_days)
        return expiration_date

    @staticmethod
    def get_days_until_expiration(expiration_date: datetime) -> int:
        """Get days until expiration (negative if expired)"""
        if not expiration_date:
            return None
        from ...utils.timezone_utils import TimezoneUtils

        # Get current UTC time for consistent comparison
        now_utc = TimezoneUtils.utc_now()

        # Convert expiration date to UTC if it has timezone info, otherwise assume UTC
        if expiration_date.tzinfo:
            expiration_utc = expiration_date.astimezone(timezone.utc)
        else:
            expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

        # Use exact time difference calculation in UTC
        time_diff_seconds = (expiration_utc - now_utc).total_seconds()
        return round(time_diff_seconds / 86400)

    @staticmethod
    def get_life_remaining_percent(entry_date: datetime, expiration_date: datetime) -> Optional[float]:
        """Calculate percentage of shelf life remaining"""
        if not entry_date or not expiration_date:
            return None

        from ...utils.timezone_utils import TimezoneUtils
        from datetime import timezone

        try:
            # Get current UTC time for consistent comparison
            now_utc = TimezoneUtils.utc_now()

            # Convert all dates to UTC for consistent calculation
            if entry_date.tzinfo:
                entry_utc = entry_date.astimezone(timezone.utc)
            else:
                entry_utc = entry_date.replace(tzinfo=timezone.utc)

            if expiration_date.tzinfo:
                expiration_utc = expiration_date.astimezone(timezone.utc)
            else:
                expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

            # Calculate exact time progression in UTC
            total_life_seconds = (expiration_utc - entry_utc).total_seconds()
            time_remaining_seconds = (expiration_utc - now_utc).total_seconds()

            if total_life_seconds <= 0:
                return 0.0

            # Calculate percentage based on time remaining vs total life
            life_remaining_percent = max(0.0, (time_remaining_seconds / total_life_seconds) * 100)
            return min(100.0, life_remaining_percent)
        except (TypeError, AttributeError) as e:
            # Handle cases where timezone conversion fails
            logger.warning(f"Timezone conversion error in get_life_remaining_percent: {e}")
            return None

    @staticmethod
    def get_effective_expiration_date(fifo_entry) -> Optional[datetime]:
        """
        Get the effective expiration date for a FIFO entry using proper hierarchy:
        1. If from batch - use batch's completed_at + batch shelf_life_days (or use greater of batch vs master)
        2. If manual entry - use entry timestamp + master inventory item shelf_life_days
        """
        # Only process perishable items
        if not fifo_entry.is_perishable:
            return None

        # Get the inventory item for master shelf life
        inventory_item = InventoryItem.query.get(fifo_entry.inventory_item_id)
        if not inventory_item:
            return None

        master_shelf_life = inventory_item.shelf_life_days if inventory_item.is_perishable else None

        # If this entry is from a batch
        if fifo_entry.batch_id:
            batch = Batch.query.get(fifo_entry.batch_id)
            if batch and batch.is_perishable and batch.shelf_life_days:
                # Use batch completion date (completed_at) as the start date
                start_date = batch.completed_at
                if start_date:
                    # Use the greater shelf life between batch and master
                    effective_shelf_life = batch.shelf_life_days
                    if master_shelf_life:
                        effective_shelf_life = max(batch.shelf_life_days, master_shelf_life)

                    return ExpirationService.calculate_expiration_date(start_date, effective_shelf_life)

        # For manual entries, use the entry timestamp + master shelf life
        if master_shelf_life and fifo_entry.timestamp:
            return ExpirationService.calculate_expiration_date(fifo_entry.timestamp, master_shelf_life)

        return None

    @staticmethod
    def get_effective_sku_expiration_date(sku_entry) -> Optional[datetime]:
        """
        Get the effective expiration date for a ProductSKU FIFO entry using proper hierarchy:
        1. If from batch - use batch's completed_at + batch shelf_life_days (or use greater of batch vs master)
        2. If manual entry - use entry timestamp + master inventory item shelf_life_days
        """
        # Only process perishable items
        if not sku_entry.is_perishable:
            return None

        # Get the inventory item for master shelf life
        inventory_item = InventoryItem.query.get(sku_entry.inventory_item_id)
        if not inventory_item:
            logger.warning(f"No inventory item found for SKU entry {sku_entry.id}")
            return None

        master_shelf_life = inventory_item.shelf_life_days if inventory_item.is_perishable else None

        # If this entry is from a batch
        if sku_entry.batch_id:
            batch = Batch.query.get(sku_entry.batch_id)
            if batch and batch.is_perishable and batch.shelf_life_days:
                # Use batch completion date (completed_at) as the start date
                start_date = batch.completed_at
                if start_date:
                    # Use the greater shelf life between batch and master
                    effective_shelf_life = batch.shelf_life_days
                    if master_shelf_life:
                        effective_shelf_life = max(batch.shelf_life_days, master_shelf_life)

                    expiration_date = ExpirationService.calculate_expiration_date(start_date, effective_shelf_life)
                    return expiration_date
                else:
                    logger.warning(f"Batch {batch.id} has no completion date")
            else:
                logger.debug(f"Batch {sku_entry.batch_id} not found or not perishable")

        # For manual entries, use the entry timestamp + master shelf life
        if master_shelf_life and sku_entry.timestamp:
            expiration_date = ExpirationService.calculate_expiration_date(sku_entry.timestamp, master_shelf_life)
            return expiration_date

        logger.debug(f"SKU entry {sku_entry.id}: No valid expiration calculation path found")
        return None

    @staticmethod
    def _query_fifo_entries(expired=False, days_ahead: int = None):
        """Query FIFO entries based on expiration criteria - only perishable items"""
        from ...utils.timezone_utils import TimezoneUtils
        from datetime import timezone

        # Use UTC for all time comparisons
        now_utc = TimezoneUtils.utc_now()

        base_filter = [
            InventoryHistory.is_perishable == True,  # Only perishable items
            InventoryHistory.remaining_quantity > 0,
            InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
        ]

        # Get FIFO entries
        fifo_entries = db.session.query(InventoryHistory).join(InventoryItem).filter(and_(*base_filter)).all()

        # Filter and calculate expiration dates using the new logic
        filtered_entries = []
        for entry in fifo_entries:
            # Calculate expiration date using proper hierarchy
            expiration_date = ExpirationService.get_effective_expiration_date(entry)

            if not expiration_date:
                continue

            # Ensure both dates are timezone-aware for comparison
            try:
                # Convert expiration date to UTC for comparison
                if expiration_date.tzinfo:
                    expiration_utc = expiration_date.astimezone(timezone.utc)
                else:
                    expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

                # Ensure now_utc is timezone-aware
                if now_utc.tzinfo is None:
                    now_utc = now_utc.replace(tzinfo=timezone.utc)

                # Apply time-based filtering using UTC
                if expired and expiration_utc < now_utc:
                    # Create entry object for compatibility
                    entry_obj = type('Entry', (), {
                        'inventory_item_id': entry.inventory_item_id,
                        'ingredient_name': entry.inventory_item.name,
                        'remaining_quantity': entry.remaining_quantity,
                        'unit': entry.unit,
                        'expiration_date': expiration_date,  # Keep original for display
                        'fifo_id': entry.id,
                        'fifo_code': entry.fifo_code,
                        'lot_number': entry.fifo_code,
                        'expiration_time': '00:00:00'
                    })()
                    filtered_entries.append(entry_obj)
                elif days_ahead:
                    future_date_utc = now_utc + timedelta(days=days_ahead)
                    if now_utc <= expiration_utc <= future_date_utc:
                        entry_obj = type('Entry', (), {
                            'inventory_item_id': entry.inventory_item_id,
                            'ingredient_name': entry.inventory_item.name,
                            'remaining_quantity': entry.remaining_quantity,
                            'unit': entry.unit,
                            'expiration_date': expiration_date,  # Keep original for display
                            'fifo_id': entry.id,
                            'fifo_code': entry.fifo_code,
                            'lot_number': entry.fifo_code,
                            'expiration_time': '00:00:00'
                        })()
                        filtered_entries.append(entry_obj)
            except (TypeError, ValueError) as e:
                logger.warning(f"Timezone comparison error for entry {entry.id}: {e}")
                continue

        return filtered_entries

    @staticmethod
    def _query_sku_entries(expired=False, days_ahead: int = None):
        """Query product SKU entries based on expiration criteria - only perishable items"""
        from ...utils.timezone_utils import TimezoneUtils
        from ...models import Product, ProductVariant, ProductSKU, ProductSKUHistory
        from datetime import timezone

        # Use UTC for all time comparisons
        now_utc = TimezoneUtils.utc_now()

        base_filter = [
            ProductSKUHistory.remaining_quantity > 0,
            ProductSKUHistory.quantity_change > 0,  # Only addition entries
            ProductSKUHistory.is_perishable == True,  # Only perishable items
            InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
        ]

        # Get SKU entries with expiration data
        sku_entries = db.session.query(ProductSKUHistory).join(
            InventoryItem, ProductSKUHistory.inventory_item_id == InventoryItem.id
        ).filter(and_(*base_filter)).all()

        # Filter by expiration criteria using new logic
        filtered_entries = []
        for sku_entry in sku_entries:
            # Calculate expiration date using proper hierarchy
            expiration_date = ExpirationService.get_effective_sku_expiration_date(sku_entry)

            if not expiration_date:
                continue

            try:
                # Convert expiration date to UTC for comparison
                if expiration_date.tzinfo:
                    expiration_utc = expiration_date.astimezone(timezone.utc)
                else:
                    expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

                # Ensure now_utc is timezone-aware
                if now_utc.tzinfo is None:
                    now_utc = now_utc.replace(tzinfo=timezone.utc)

                # Apply time-based filtering using UTC
                if expired and expiration_utc < now_utc:
                    filtered_entries.append(sku_entry)
                elif days_ahead:
                    future_date_utc = now_utc + timedelta(days=days_ahead)
                    if now_utc <= expiration_utc <= future_date_utc:
                        filtered_entries.append(sku_entry)
            except (TypeError, ValueError) as e:
                logger.warning(f"Timezone comparison error for SKU entry {sku_entry.id}: {e}")
                continue

        return filtered_entries

    @staticmethod
    def _format_sku_entry(sku_entry):
        """Format SKU entry for consistent return structure"""
        # Calculate expiration date using new hierarchy logic
        expiration_date = ExpirationService.get_effective_sku_expiration_date(sku_entry)

        if expiration_date:
            # Get product info
            from ...models import Product, ProductVariant, ProductSKU
            sku = ProductSKU.query.filter_by(inventory_item_id=sku_entry.inventory_item_id).first()
            if not sku:
                logger.warning(f"No SKU found for inventory_item_id {sku_entry.inventory_item_id}")
                return None

            product = Product.query.get(sku.product_id)
            variant = ProductVariant.query.get(sku.variant_id)

            return {
                'inventory_item_id': sku_entry.inventory_item_id,
                'product_name': product.name if product else 'Unknown Product',
                'variant_name': variant.name if variant else 'Unknown Variant',
                'size_label': sku.size_label if sku else 'Unknown Size',
                'quantity': sku_entry.remaining_quantity,
                'unit': sku_entry.unit,
                'expiration_date': expiration_date,  # Keep as datetime object for template calculations
                'history_id': sku_entry.id,
                'product_inv_id': sku_entry.id,
                'product_id': sku.product_id if sku else None,
                'variant_id': sku.variant_id if sku else None,
                'lot_number': f"LOT-{sku_entry.id}"
            }

    @staticmethod
    def get_expired_inventory_items() -> Dict:
        """Get all expired inventory items across the system using dynamic expiration calculation"""
        # Use the same logic as the private methods but for expired items
        expired_fifo_entries = ExpirationService._query_fifo_entries(expired=True)
        expired_sku_entries = ExpirationService._query_sku_entries(expired=True)

        # Format SKU entries for consistency
        expired_products = []
        for sku in expired_sku_entries:
            formatted = ExpirationService._format_sku_entry(sku)
            if formatted:
                expired_products.append(formatted)

        return {
            'fifo_entries': expired_fifo_entries,
            'product_inventory': expired_products
        }

    @staticmethod
    def get_expiring_soon_items(days_ahead: int = 7) -> Dict:
        """Get items expiring within specified days using dynamic expiration calculation"""
        # Use the same logic as the private methods but for expiring soon items
        expiring_fifo_entries = ExpirationService._query_fifo_entries(days_ahead=days_ahead)
        expiring_sku_entries = ExpirationService._query_sku_entries(days_ahead=days_ahead)

        # Format SKU entries for consistency
        expiring_products = []
        for sku in expiring_sku_entries:
            formatted = ExpirationService._format_sku_entry(sku)
            if formatted:
                expiring_products.append(formatted)

        return {
            'fifo_entries': expiring_fifo_entries,
            'product_inventory': expiring_products
        }

    @staticmethod
    def update_fifo_expiration_data(inventory_item_id: int, shelf_life_days: int):
        """Update expiration data for all FIFO entries with remaining quantity"""
        # Note: This should NOT set expiration_date directly on FIFO entries
        # The expiration date should be calculated dynamically using get_effective_expiration_date

        # Update the master inventory item
        item = InventoryItem.query.get(inventory_item_id)
        if item:
            item.is_perishable = True
            item.shelf_life_days = shelf_life_days

        # Update FIFO entries to mark as perishable but let expiration be calculated dynamically
        entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).all()

        for entry in entries:
            entry.is_perishable = True
            entry.shelf_life_days = shelf_life_days
            # Do NOT set expiration_date here - it should be calculated dynamically

        db.session.commit()

    @staticmethod
    def get_expiration_date_for_new_entry(inventory_item_id: int, batch_id: Optional[int] = None) -> Optional[datetime]:
        """
        Calculate expiration date for a new FIFO entry being created
        This is used when creating new inventory history entries
        """
        inventory_item = InventoryItem.query.get(inventory_item_id)
        if not inventory_item or not inventory_item.is_perishable:
            return None

        master_shelf_life = inventory_item.shelf_life_days
        from ...utils.timezone_utils import TimezoneUtils

        # Use UTC for consistency in calculations
        now_utc = TimezoneUtils.utc_now()

        # If this entry is from a batch
        if batch_id:
            batch = Batch.query.get(batch_id)
            if batch and batch.is_perishable and batch.shelf_life_days:
                # Use batch completion date (completed_at) as the start date
                start_date = batch.completed_at or now_utc

                # Ensure start_date is in UTC
                if start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)
                elif start_date.tzinfo != timezone.utc:
                    start_date = start_date.astimezone(timezone.utc)

                # Use the greater shelf life between batch and master
                effective_shelf_life = batch.shelf_life_days
                if master_shelf_life:
                    effective_shelf_life = max(batch.shelf_life_days, master_shelf_life)

                return ExpirationService.calculate_expiration_date(start_date, effective_shelf_life)

        # For manual entries, use current UTC time + master shelf life
        if master_shelf_life:
            return ExpirationService.calculate_expiration_date(now_utc, master_shelf_life)

        return None

    @staticmethod
    def get_inventory_item_expiration_status(inventory_item_id: int):
        """Get expiration status for a specific inventory item"""
        from ...utils.timezone_utils import TimezoneUtils
        from datetime import timezone

        # Use UTC for all time comparisons
        now_utc = TimezoneUtils.utc_now()
        future_date_utc = now_utc + timedelta(days=7)

        # Get all FIFO entries for this item with organization scoping
        entries = db.session.query(InventoryHistory).join(InventoryItem).filter(
            and_(
                InventoryHistory.inventory_item_id == inventory_item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.is_perishable == True,
                InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
            )
        ).all()

        expired_entries = []
        expiring_soon_entries = []

        for entry in entries:
            expiration_date = ExpirationService.get_effective_expiration_date(entry)
            if expiration_date:
                # Convert expiration date to UTC for comparison
                if expiration_date.tzinfo:
                    expiration_utc = expiration_date.astimezone(timezone.utc)
                else:
                    expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

                if expiration_utc < now_utc:
                    expired_entries.append(entry)
                elif expiration_utc <= future_date_utc:
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
                InventoryItem.organization_id == current_user.organization_id if current_user.is_authenticated and current_user.organization_id else True
            )
        ).all()

        if not entries:
            return None

        total_weighted_freshness = 0.0
        total_quantity = 0.0

        for entry in entries:
            expiration_date = ExpirationService.get_effective_expiration_date(entry)
            if expiration_date and entry.timestamp:
                # Calculate freshness percentage
                life_remaining_percent = ExpirationService.get_life_remaining_percent(
                    entry.timestamp, expiration_date
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
                from ...models.product import ProductSKUHistory
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

    @staticmethod
    def get_expiring_within_days(days_ahead: int = 7) -> List[Dict]:
        """Get items expiring within specified days with proper organization scoping"""
        try:
            # Calculate the future date
            future_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)

            # Query ingredients with organization scoping
            query = db.session.query(InventoryItem).filter(
                InventoryItem.expiration_date.isnot(None),
                InventoryItem.expiration_date <= future_date,
                InventoryItem.quantity > 0
            )

            # Apply organization scoping
            if current_user.is_authenticated and current_user.organization_id:
                query = query.filter(InventoryItem.organization_id == current_user.organization_id)
            elif current_user.user_type == 'developer':
                # Developers can see all or selected org
                from flask import session
                selected_org_id = session.get('dev_selected_org_id')
                if selected_org_id:
                    query = query.filter(InventoryItem.organization_id == selected_org_id)

            # Order by expiration date
            items = query.order_by(InventoryItem.expiration_date.asc()).all()

            results = []
            for item in items:
                # Calculate days until expiration
                if item.expiration_date:
                    days_left = (item.expiration_date.date() - datetime.now(timezone.utc).date()).days
                    expiration_time = item.expiration_date.strftime('%H:%M:%S') if item.expiration_date else '00:00:00'
                else:
                    days_left = None
                    expiration_time = '00:00:00'

                results.append({
                    'id': item.id,
                    'ingredient_name': item.ingredient_name or 'Unknown Ingredient',
                    'quantity': float(item.quantity) if item.quantity else 0.0,
                    'unit': item.unit or '',
                    'lot_number': item.lot_number or '-',
                    'expiration_date': item.expiration_date.date() if item.expiration_date else None,
                    'expiration_time': expiration_time,
                    'days_left': days_left,
                    'fifo_code': item.fifo_code or f"#{item.id}"
                })

            return results

        except Exception as e:
            logging.error(f"Error getting expiring items: {e}")
            return []