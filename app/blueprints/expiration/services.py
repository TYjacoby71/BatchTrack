"""Expiration calculation services.

Synopsis:
Compute expiration dates, remaining life, and expiration summaries.

Glossary:
- Shelf life: Days an item remains valid after receipt.
- Expiration date: Timestamp when an item becomes expired.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload

from app.services.inventory_adjustment import process_inventory_adjustment

from ...models import (
    Batch,
    InventoryHistory,
    InventoryItem,
    InventoryLot,
    ProductSKU,
    UnifiedInventoryHistory,
    db,
)

# Set logger to INFO level to reduce debug noise
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# --- Expiration service ---
# Purpose: Provide expiration calculations and inventory queries.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
class ExpirationService:
    """Centralized service for expiration calculations and data fetching using InventoryLot objects where possible"""

    @staticmethod
    def calculate_expiration_date(
        start_date: datetime, shelf_life_days: int
    ) -> datetime:
        """Calculate expiration date from start date and shelf life"""
        if not start_date or not shelf_life_days:
            return None

        # Ensure we have a proper datetime object
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

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
    def get_life_remaining_percent(
        entry_date: datetime, shelf_life_days: int
    ) -> Optional[float]:
        """Calculate percentage of shelf life remaining based on days since creation"""
        if not entry_date or not shelf_life_days:
            return None

        from datetime import timezone

        from ...utils.timezone_utils import TimezoneUtils

        try:
            # Get current UTC time for consistent comparison
            now_utc = TimezoneUtils.utc_now()

            # Ensure entry_date is timezone-aware (convert to UTC if naive)
            if entry_date.tzinfo is None:
                entry_date = entry_date.replace(tzinfo=timezone.utc)
            elif entry_date.tzinfo != timezone.utc:
                entry_date = entry_date.astimezone(timezone.utc)

            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)

            # Calculate precise time elapsed in seconds for accurate freshness
            time_elapsed_seconds = (now_utc - entry_date).total_seconds()
            total_shelf_life_seconds = (
                shelf_life_days * 24 * 60 * 60
            )  # Convert days to seconds

            # Calculate remaining life percentage based on precise time
            remaining_seconds = total_shelf_life_seconds - time_elapsed_seconds
            life_remaining_percent = (
                remaining_seconds / total_shelf_life_seconds
            ) * 100

            # Clamp between 0 and 100
            return max(0.0, min(100.0, life_remaining_percent))
        except (TypeError, AttributeError) as e:
            # Handle cases where date calculation fails
            logger.warning(f"Date calculation error in get_life_remaining_percent: {e}")
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
        inventory_item = db.session.get(InventoryItem, fifo_entry.inventory_item_id)
        if not inventory_item:
            return None

        master_shelf_life = (
            inventory_item.shelf_life_days if inventory_item.is_perishable else None
        )

        # If this entry is from a batch
        if fifo_entry.batch_id:
            batch = db.session.get(Batch, fifo_entry.batch_id)
            if batch and batch.is_perishable and batch.shelf_life_days:
                # Use batch completion date (completed_at) as the start date
                start_date = batch.completed_at
                if start_date:
                    # Use the greater shelf life between batch and master
                    effective_shelf_life = batch.shelf_life_days
                    if master_shelf_life:
                        effective_shelf_life = max(
                            batch.shelf_life_days, master_shelf_life
                        )

                    return ExpirationService.calculate_expiration_date(
                        start_date, effective_shelf_life
                    )

        # For manual entries, use the entry timestamp + master shelf life
        if master_shelf_life and fifo_entry.timestamp:
            return ExpirationService.calculate_expiration_date(
                fifo_entry.timestamp, master_shelf_life
            )

        return None

    @staticmethod
    def get_effective_sku_expiration_date(lot) -> Optional[datetime]:
        """
        Get the effective expiration date for a product InventoryLot using proper hierarchy:
        1. If from batch - use batch's completed_at + batch shelf_life_days (or use greater of batch vs master)
        2. If manual entry - use lot.received_date + master inventory item shelf_life_days
        """
        if not lot:
            return None

        # Only process perishable items
        inventory_item = lot.inventory_item or db.session.get(
            InventoryItem, lot.inventory_item_id
        )
        if not inventory_item or not inventory_item.is_perishable:
            return None

        # If the lot already has an explicit expiration date, trust it
        if lot.expiration_date:
            return lot.expiration_date

        master_shelf_life = (
            inventory_item.shelf_life_days if inventory_item.is_perishable else None
        )

        # If this entry is from a batch
        if lot.batch_id:
            batch = db.session.get(Batch, lot.batch_id)
            if batch and batch.is_perishable and batch.shelf_life_days:
                # Use batch completion date (completed_at) as the start date
                start_date = batch.completed_at
                if start_date:
                    # Use the greater shelf life between batch and master
                    effective_shelf_life = batch.shelf_life_days
                    if master_shelf_life:
                        effective_shelf_life = max(
                            batch.shelf_life_days, master_shelf_life
                        )

                    expiration_date = ExpirationService.calculate_expiration_date(
                        start_date, effective_shelf_life
                    )
                    return expiration_date
                else:
                    logger.warning(f"Batch {batch.id} has no completion date")
            else:
                logger.debug(f"Batch {lot.batch_id} not found or not perishable")

        # For manual entries, use the lot received date + master shelf life
        if master_shelf_life and lot.received_date:
            expiration_date = ExpirationService.calculate_expiration_date(
                lot.received_date, master_shelf_life
            )
            return expiration_date

        logger.debug(f"Lot {lot.id}: No valid expiration calculation path found")
        return None

    @staticmethod
    def _query_fifo_entries(expired=False, days_ahead: int = None):
        """Query inventory lots based on expiration criteria for perishable items"""
        from app.models.inventory_lot import InventoryLot

        from ...utils.timezone_utils import TimezoneUtils

        now_utc = TimezoneUtils.utc_now()

        # Base lot query with remaining quantity and org scoping - ensure relationship is loaded
        query = (
            InventoryLot.scoped()
            .join(InventoryItem)
            .options(joinedload(InventoryLot.inventory_item))
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.is_perishable,
                )
            )
        )

        # Apply time-based filtering
        if expired:
            query = query.filter(
                and_(
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < now_utc,
                )
            )
        elif days_ahead:
            future_date_utc = now_utc + timedelta(days=days_ahead)
            query = query.filter(
                and_(
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date >= now_utc,
                    InventoryLot.expiration_date <= future_date_utc,
                )
            )

        lots = query.order_by(InventoryLot.expiration_date.asc()).all()

        # Format lot entries for compatibility with templates that expect FIFO-like objects
        formatted_entries = []
        for lot in lots:
            entry_obj = type(
                "Entry",
                (),
                {
                    "inventory_item_id": lot.inventory_item_id,
                    "ingredient_name": (
                        lot.inventory_item.name
                        if lot.inventory_item
                        else "Unknown Ingredient"
                    ),
                    "remaining_quantity": lot.remaining_quantity,
                    "unit": lot.unit,
                    "expiration_date": lot.expiration_date,
                    "fifo_id": lot.id,
                    "fifo_code": lot.fifo_code or f"LOT-{lot.id}",
                    "lot_number": lot.fifo_code or f"LOT-{lot.id}",
                    "expiration_time": (
                        lot.expiration_date.strftime("%H:%M:%S")
                        if lot.expiration_date
                        else "00:00:00"
                    ),
                },
            )()
            formatted_entries.append(entry_obj)

        return formatted_entries

    @staticmethod
    def _query_sku_entries(expired=False, days_ahead: int = None):
        """Query product SKU lots based on expiration criteria"""
        from datetime import timezone

        from ...utils.timezone_utils import TimezoneUtils

        now_utc = TimezoneUtils.utc_now()

        query = (
            InventoryLot.scoped()
            .join(InventoryItem, InventoryLot.inventory_item_id == InventoryItem.id)
            .join(
                ProductSKU,
                ProductSKU.inventory_item_id == InventoryLot.inventory_item_id,
            )
            .options(joinedload(InventoryLot.inventory_item))
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryItem.type == "product",
                    InventoryItem.is_perishable,
                )
            )
        )

        lots = query.all()
        filtered_entries = []

        for lot in lots:
            expiration_date = ExpirationService.get_effective_sku_expiration_date(lot)

            if not expiration_date:
                continue

            try:
                if expiration_date.tzinfo:
                    expiration_utc = expiration_date.astimezone(timezone.utc)
                else:
                    expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

                if now_utc.tzinfo is None:
                    now_utc = now_utc.replace(tzinfo=timezone.utc)

                if expired and expiration_utc < now_utc:
                    filtered_entries.append(lot)
                elif days_ahead:
                    future_date_utc = now_utc + timedelta(days=days_ahead)
                    if now_utc <= expiration_utc <= future_date_utc:
                        filtered_entries.append(lot)
                elif not expired and days_ahead is None:
                    filtered_entries.append(lot)
            except (TypeError, ValueError) as e:
                logger.warning(f"Timezone comparison error for lot {lot.id}: {e}")
                continue

        return filtered_entries

    @staticmethod
    def _format_sku_entry(lot):
        """Format SKU entry for consistent return structure"""
        # Calculate expiration date using new hierarchy logic
        expiration_date = ExpirationService.get_effective_sku_expiration_date(lot)

        if expiration_date:
            # Get product info
            from ...models import Product, ProductSKU, ProductVariant

            sku = ProductSKU.scoped().filter_by(
                inventory_item_id=lot.inventory_item_id
            ).first()
            if not sku:
                logger.warning(
                    f"No SKU found for inventory_item_id {lot.inventory_item_id}"
                )
                return None

            product = db.session.get(Product, sku.product_id)
            variant = db.session.get(ProductVariant, sku.variant_id)

            return {
                "inventory_item_id": lot.inventory_item_id,
                "product_name": product.name if product else "Unknown Product",
                "variant_name": variant.name if variant else "Unknown Variant",
                "size_label": sku.size_label if sku else "Unknown Size",
                "quantity": float(lot.remaining_quantity or 0.0),
                "unit": lot.unit,
                "expiration_date": expiration_date,  # Keep as datetime object for template calculations
                "history_id": lot.id,
                "product_inv_id": lot.id,
                "product_id": sku.product_id if sku else None,
                "variant_id": sku.variant_id if sku else None,
                "lot_number": lot.fifo_code or f"LOT-{lot.id}",
            }

    @staticmethod
    def get_expired_inventory_items() -> Dict:
        """Get all expired inventory items, including product lots"""
        expired_fifo_entries = ExpirationService._query_fifo_entries(expired=True)
        expired_sku_entries = ExpirationService._query_sku_entries(expired=True)

        # Format SKU entries for consistency
        expired_products = []
        for sku in expired_sku_entries:
            formatted = ExpirationService._format_sku_entry(sku)
            if formatted:
                expired_products.append(formatted)

        return {
            "fifo_entries": expired_fifo_entries,
            "product_inventory": expired_products,
        }

    @staticmethod
    def get_expiring_soon_items(days_ahead: int = 7) -> Dict:
        """Get items expiring within specified days, including product lots"""
        expiring_fifo_entries = ExpirationService._query_fifo_entries(
            days_ahead=days_ahead
        )
        expiring_sku_entries = ExpirationService._query_sku_entries(
            days_ahead=days_ahead
        )

        # Format SKU entries for consistency
        expiring_products = []
        for sku in expiring_sku_entries:
            formatted = ExpirationService._format_sku_entry(sku)
            if formatted:
                expiring_products.append(formatted)

        return {
            "fifo_entries": expiring_fifo_entries,
            "product_inventory": expiring_products,
        }

    @staticmethod
    def update_fifo_expiration_data(inventory_item_id: int, shelf_life_days: int):
        """Update expiration data for inventory item - updates master item and existing lots metadata"""
        # Update the master inventory item
        item = db.session.get(InventoryItem, inventory_item_id)
        if item:
            item.is_perishable = True
            item.shelf_life_days = shelf_life_days

        # Update existing lots to reflect perishable status and set expiration if missing
        lots = InventoryLot.scoped().filter(
            and_(
                InventoryLot.inventory_item_id == inventory_item_id,
                InventoryLot.remaining_quantity_base > 0,
            )
        ).all()

        for lot in lots:
            lot.shelf_life_days = shelf_life_days
            if not lot.expiration_date and lot.received_date:
                lot.expiration_date = ExpirationService.calculate_expiration_date(
                    lot.received_date, shelf_life_days
                )

        db.session.commit()

    @staticmethod
    def get_expiration_date_for_new_entry(
        inventory_item_id: int, batch_id: Optional[int] = None
    ) -> Optional[datetime]:
        """Calculate expiration date for a new lot being created (for InventoryLot creation)"""
        inventory_item = db.session.get(InventoryItem, inventory_item_id)
        if not inventory_item or not inventory_item.is_perishable:
            return None

        master_shelf_life = inventory_item.shelf_life_days
        from ...utils.timezone_utils import TimezoneUtils

        # Use UTC for consistency in calculations
        now_utc = TimezoneUtils.utc_now()

        # If this entry is from a batch
        if batch_id:
            batch = db.session.get(Batch, batch_id)
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

                return ExpirationService.calculate_expiration_date(
                    start_date, effective_shelf_life
                )

        # For manual entries, use current UTC time + master shelf life
        if master_shelf_life:
            return ExpirationService.calculate_expiration_date(
                now_utc, master_shelf_life
            )

        return None

    @staticmethod
    def get_inventory_item_expiration_status(inventory_item_id: int):
        """Get expiration status for a specific inventory item using InventoryLot"""
        from app.models.inventory_lot import InventoryLot

        from ...utils.timezone_utils import TimezoneUtils

        now_utc = TimezoneUtils.utc_now()
        future_date_utc = now_utc + timedelta(days=7)

        # Query lots for this item with org scoping
        base_filter = [
            InventoryLot.inventory_item_id == inventory_item_id,
            InventoryLot.remaining_quantity_base > 0,
            InventoryLot.expiration_date.isnot(None),
        ]

        if current_user.is_authenticated and current_user.organization_id:
            base_filter.append(
                InventoryLot.organization_id == current_user.organization_id
            )

        lots = InventoryLot.scoped().filter(and_(*base_filter)).all()

        expired_lots = []
        expiring_soon_lots = []

        for lot in lots:
            if lot.expiration_date:
                if lot.expiration_date < now_utc:
                    expired_lots.append(lot)
                elif lot.expiration_date <= future_date_utc:
                    expiring_soon_lots.append(lot)

        return {
            "expired_entries": expired_lots,
            "expiring_soon_entries": expiring_soon_lots,
            "has_expiration_issues": len(expired_lots) > 0
            or len(expiring_soon_lots) > 0,
        }

    @staticmethod
    def get_weighted_average_freshness(inventory_item_id: int) -> Optional[float]:
        """Calculate weighted average freshness for an inventory item based on InventoryLot objects"""
        from app.models.inventory_lot import InventoryLot

        lots = (
            InventoryLot.scoped()
            .filter(
                and_(
                    InventoryLot.inventory_item_id == inventory_item_id,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                )
            )
            .all()
        )

        if not lots:
            return None

        total_weighted_freshness = 0.0
        total_quantity = 0.0

        for lot in lots:
            if lot.expiration_date and lot.received_date and lot.shelf_life_days:
                life_remaining_percent = ExpirationService.get_life_remaining_percent(
                    lot.received_date, lot.shelf_life_days
                )
                if life_remaining_percent is not None:
                    total_weighted_freshness += life_remaining_percent * float(
                        lot.remaining_quantity
                    )
                    total_quantity += float(lot.remaining_quantity)

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
            "expired_count": len(expired_items["fifo_entries"])
            + len(expired_items["product_inventory"]),
            "expiring_soon_count": len(expiring_soon["fifo_entries"])
            + len(expiring_soon["product_inventory"]),
            "total_expiration_issues": len(expired_items["fifo_entries"])
            + len(expired_items["product_inventory"])
            + len(expiring_soon["fifo_entries"])
            + len(expiring_soon["product_inventory"]),
        }

    @staticmethod
    def mark_as_expired(kind, entry_id, quantity=None, notes=""):
        """Mark inventory as expired and remove from stock - supports lots and legacy entries"""
        try:
            if kind in ("fifo", "raw"):
                # Use InventoryLot for lot-based tracking
                try:
                    lot = db.session.get(InventoryLot, entry_id)
                except OperationalError:
                    lot = None
                # Fallback to UnifiedInventoryHistory for canonical FIFO entries
                if lot:
                    entry = None
                else:
                    try:
                        entry = db.session.get(UnifiedInventoryHistory, entry_id)
                    except OperationalError:
                        entry = None
                # Legacy compatibility - some tests/bootstrap data still use InventoryHistory
                if not entry and not lot:
                    entry = db.session.get(InventoryHistory, entry_id)

                if not entry and not lot:
                    return False, "Lot or FIFO entry not found"

                inv_id = entry.inventory_item_id if entry else lot.inventory_item_id
                unit = entry.unit if entry else lot.unit
                remaining = (
                    entry.remaining_quantity if entry else lot.remaining_quantity
                )
                use_qty = float(remaining if quantity is None else quantity)

                result = process_inventory_adjustment(
                    item_id=inv_id,
                    quantity=-use_qty,
                    change_type="spoil",
                    unit=unit,
                    notes=f"Expired lot disposal #{entry_id}: {notes}",
                    created_by=(
                        current_user.id
                        if getattr(current_user, "is_authenticated", False)
                        else None
                    ),
                )

                # Align message with existing expectations
                return result, (
                    "Successfully marked FIFO entry as expired"
                    if entry
                    else "Successfully marked lot as expired"
                )

            elif kind == "product":
                lot = db.session.get(InventoryLot, entry_id)
                if not lot:
                    return False, "Product lot not found"

                use_qty = float(
                    lot.remaining_quantity if quantity is None else quantity
                )

                result = process_inventory_adjustment(
                    item_id=lot.inventory_item_id,
                    quantity=-use_qty,
                    change_type="spoil",
                    unit=lot.unit,
                    notes=f"Expired product lot disposal #{entry_id}: {notes}",
                    created_by=(
                        current_user.id
                        if getattr(current_user, "is_authenticated", False)
                        else None
                    ),
                )
                return result, "Successfully marked product FIFO entry as expired"

            return False, "Invalid expiration type"

        except Exception as e:
            logger.warning("Suppressed exception fallback at app/blueprints/expiration/services.py:685", exc_info=True)
            return False, f"Error marking as expired: {str(e)}"

    @staticmethod
    def get_expiring_within_days(days_ahead: int = 7) -> List[Dict]:
        """Get items expiring within specified days using InventoryLot with org scoping"""
        try:
            from ...utils.timezone_utils import TimezoneUtils

            now_utc = TimezoneUtils.utc_now()
            future_date = now_utc + timedelta(days=days_ahead)

            # Query inventory lots with organization scoping and perishable via InventoryItem
            query = (
                InventoryLot.scoped()
                .join(InventoryItem)
                .filter(
                    and_(
                        InventoryLot.expiration_date.isnot(None),
                        InventoryLot.expiration_date >= now_utc,
                        InventoryLot.expiration_date <= future_date,
                        InventoryLot.remaining_quantity_base > 0,
                        InventoryItem.is_perishable,
                    )
                )
            )

            lots = query.order_by(InventoryLot.expiration_date.asc()).all()

            results = []
            for lot in lots:
                # Calculate days until expiration
                if lot.expiration_date:
                    days_left = (
                        lot.expiration_date.date() - datetime.now(timezone.utc).date()
                    ).days
                    expiration_time = (
                        lot.expiration_date.strftime("%H:%M:%S")
                        if lot.expiration_date
                        else "00:00:00"
                    )
                else:
                    days_left = None
                    expiration_time = "00:00:00"

                results.append(
                    {
                        "id": lot.id,
                        "ingredient_name": (
                            lot.inventory_item.name
                            if lot.inventory_item
                            else "Unknown Ingredient"
                        ),
                        "quantity": (
                            float(lot.remaining_quantity)
                            if lot.remaining_quantity
                            else 0.0
                        ),
                        "unit": lot.unit or "",
                        "lot_number": lot.lot_number or f"LOT-{lot.id}",
                        "expiration_date": (
                            lot.expiration_date.date() if lot.expiration_date else None
                        ),
                        "expiration_time": expiration_time,
                        "days_left": days_left,
                        "fifo_code": lot.fifo_code or f"#{lot.id}",
                    }
                )

            return results

        except Exception as e:
            logging.error(f"Error getting expiring items: {e}")
            return []

    @staticmethod
    def get_expired_inventory():
        """Get all expired inventory items using InventoryLot with org scoping"""
        from ...utils.timezone_utils import TimezoneUtils

        now_utc = TimezoneUtils.utc_now()

        query = (
            InventoryLot.scoped()
            .join(InventoryItem)
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date < now_utc,
                    InventoryItem.is_perishable,
                )
            )
        )

        return query.all()

    @staticmethod
    def get_expiring_soon(days_ahead=7):
        """Get inventory expiring within the specified days using InventoryLot with org scoping"""
        from ...utils.timezone_utils import TimezoneUtils

        now_utc = TimezoneUtils.utc_now()
        cutoff_date_utc = now_utc + timedelta(days=days_ahead)

        query = (
            InventoryLot.scoped()
            .join(InventoryItem)
            .filter(
                and_(
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.expiration_date.isnot(None),
                    InventoryLot.expiration_date > now_utc,
                    InventoryLot.expiration_date <= cutoff_date_utc,
                    InventoryItem.is_perishable,
                )
            )
        )

        return query.all()
