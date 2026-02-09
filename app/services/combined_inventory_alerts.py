"""Combined inventory alert service.

Synopsis:
Compute expiration, low-stock, and out-of-stock alerts for ingredients and product SKUs.
Gate SKU alerts on inventory activity so never-stocked items do not trigger.

Glossary:
- Expiration alert: Warning for expired or expiring lots.
- Low stock: Inventory below configured thresholds.
"""

from ..models import db, InventoryItem, ProductSKU
from ..models.inventory_lot import InventoryLot
from sqlalchemy import and_, or_
from typing import List, Dict
from datetime import timedelta
from flask_login import current_user

# --- Combined inventory alerts ---
# Purpose: Compute unified expiration and product alerts.
class CombinedInventoryAlertService:
    """Unified service for all inventory alerts - raw materials and products.

    Purpose: Provide SKU- and inventory-based alert queries plus summary payloads for dashboards and alert views.
    """

    @staticmethod
    def get_expiration_alerts(days_ahead: int = 7) -> Dict:
        """Purpose: Return expired and expiring inventory lots and product items within the alert window."""
        import logging
        try:
            from ..models import InventoryItem, UnifiedInventoryHistory
            from ..utils.timezone_utils import TimezoneUtils
            from flask_login import current_user
            from ..models.inventory_lot import InventoryLot

            current_time = TimezoneUtils.utc_now()
            expiration_cutoff = current_time + timedelta(days=days_ahead)

            # Get expired FIFO entries (using InventoryLot)
            expired_fifo_entries = db.session.query(InventoryLot).filter(
                and_(
                    InventoryLot.expiration_date < current_time,
                    InventoryLot.remaining_quantity_base > 0,
                    InventoryLot.organization_id == current_user.organization_id if current_user.organization_id else True
                )
            ).all()

            # Get expiring soon FIFO entries (using InventoryLot)
            expiring_fifo_entries = db.session.query(InventoryLot).filter(
                and_(
                    InventoryLot.expiration_date >= current_time,
                    InventoryLot.expiration_date <= expiration_cutoff,
                    InventoryLot.remaining_quantity_base > 0
                ),
                InventoryLot.organization_id == current_user.organization_id if current_user.organization_id else True
            ).all()

            # Get expired product inventory items
            expired_products = db.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.expiration_date < current_time,
                    InventoryItem.type.in_(['product', 'product-reserved'])
                ),
                InventoryItem.organization_id == current_user.organization_id if current_user.organization_id else True
            ).all()

            # Get expiring soon product inventory items
            expiring_products = db.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.expiration_date >= current_time,
                    InventoryItem.expiration_date <= expiration_cutoff,
                    InventoryItem.type.in_(['product', 'product-reserved'])
                ),
                InventoryItem.organization_id == current_user.organization_id if current_user.organization_id else True
            ).all()

            # Calculate totals
            expired_total = len(expired_fifo_entries) + len(expired_products)
            expiring_soon_total = len(expiring_fifo_entries) + len(expiring_products)

            # Debug logging
            logging.info(f"Expiration alerts debug: expired_fifo={len(expired_fifo_entries)}, expired_products={len(expired_products)}, expiring_fifo={len(expiring_fifo_entries)}, expiring_products={len(expiring_products)}")
            logging.info(f"Current time: {current_time}, cutoff: {expiration_cutoff}")

            return {
                'expired_fifo_entries': expired_fifo_entries,
                'expired_products': expired_products,
                'expiring_fifo_entries': expiring_fifo_entries,
                'expiring_products': expiring_products,
                'expired_total': expired_total,
                'expiring_soon_total': expiring_soon_total,
                'has_any_expiration_issues': expired_total > 0 or expiring_soon_total > 0
            }
        except Exception as e:
            logging.error(f"Error getting expiration alerts: {e}")
            # Return empty dict on error to prevent dashboard crashing
            return {
                'expired_fifo_entries': [],
                'expired_products': [],
                'expiring_fifo_entries': [],
                'expiring_products': [],
                'expired_total': 0,
                'expiring_soon_total': 0,
                'has_any_expiration_issues': False
            }

    @staticmethod
    def get_low_stock_ingredients():
        """Purpose: Return ingredient and container items that are below their configured thresholds."""
        from flask_login import current_user
        # Query InventoryItem for raw materials with low stock thresholds
        # Then check if total remaining quantity across all lots is below threshold
        query = InventoryItem.query.filter(
            and_(
                InventoryItem.low_stock_threshold > 0,
                InventoryItem.quantity <= InventoryItem.low_stock_threshold,
                ~InventoryItem.type.in_(['product', 'product-reserved'])
            )
        )
        # Apply organization scoping
        if current_user and current_user.is_authenticated:
            if current_user.organization_id:
                query = query.filter(InventoryItem.organization_id == current_user.organization_id)
            # Developer users without organization_id see all data
        else:
            # If not authenticated, return empty result
            return []
        return query.all()

    @staticmethod
    def get_low_stock_skus():
        """Purpose: Return SKU low-stock alerts using SKU thresholds and activity gating."""
        from flask_login import current_user
        from ..models.inventory import InventoryHistory
        history_exists = db.session.query(InventoryHistory.id).filter(
            InventoryHistory.inventory_item_id == InventoryItem.id
        ).exists()
        query = ProductSKU.query.join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.type.in_(['product', 'product-reserved']),
                ProductSKU.is_active == True,
                ProductSKU.is_product_active == True,
                ProductSKU.low_stock_threshold > 0,
                InventoryItem.quantity <= ProductSKU.low_stock_threshold,
                or_(InventoryItem.quantity != 0, history_exists)
            )
        )
        # Apply organization scoping
        if current_user and current_user.is_authenticated:
            if current_user.organization_id:
                query = query.filter(ProductSKU.organization_id == current_user.organization_id)
            # Developer users without organization_id see all data
        else:
            # If not authenticated, return empty result
            return []
        return query.all()

    @staticmethod
    def get_out_of_stock_skus():
        """Purpose: Return SKU out-of-stock alerts once inventory activity exists."""
        from flask_login import current_user
        from ..models.inventory import InventoryHistory
        history_exists = db.session.query(InventoryHistory.id).filter(
            InventoryHistory.inventory_item_id == InventoryItem.id
        ).exists()
        query = ProductSKU.query.join(
            InventoryItem, ProductSKU.inventory_item_id == InventoryItem.id
        ).filter(
            and_(
                InventoryItem.type.in_(['product', 'product-reserved']),
                ProductSKU.is_active == True,
                ProductSKU.is_product_active == True,
                InventoryItem.quantity == 0,
                history_exists
            )
        )
        # Apply organization scoping
        if current_user and current_user.is_authenticated:
            if current_user.organization_id:
                query = query.filter(ProductSKU.organization_id == current_user.organization_id)
            # Developer users without organization_id see all data
        else:
            # If not authenticated, return empty result
            return []
        return query.all()

    @staticmethod
    def get_unified_stock_summary() -> Dict:
        """Purpose: Aggregate ingredient and SKU alerts into dashboard-ready counts and groupings."""
        # Get raw material alerts
        low_stock_ingredients = CombinedInventoryAlertService.get_low_stock_ingredients()

        # Get product alerts (these are SKU-level objects)
        low_stock_product_items = CombinedInventoryAlertService.get_low_stock_skus()
        out_of_stock_product_items = CombinedInventoryAlertService.get_out_of_stock_skus()

        # Group products by name to avoid duplicates
        low_stock_products = {}
        out_of_stock_products = {}

        for item in low_stock_product_items:
            product_name = item.product_name or (item.product.name if item.product else None)
            if not product_name:
                product_name = item.sku_name or item.sku
            if product_name not in low_stock_products:
                low_stock_products[product_name] = []
            low_stock_products[product_name].append(item)

        for item in out_of_stock_product_items:
            product_name = item.product_name or (item.product.name if item.product else None)
            if not product_name:
                product_name = item.sku_name or item.sku
            if product_name not in out_of_stock_products:
                out_of_stock_products[product_name] = []
            out_of_stock_products[product_name].append(item)

        return {
            # Raw materials
            'low_stock_ingredients': low_stock_ingredients,
            'low_stock_ingredients_count': len(low_stock_ingredients),

            # Products (SKU-level objects)
            'low_stock_skus': low_stock_product_items,
            'out_of_stock_skus': out_of_stock_product_items,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'low_stock_count': len(low_stock_product_items),
            'out_of_stock_count': len(out_of_stock_product_items),
            'affected_products_count': len(set(low_stock_products.keys()) | set(out_of_stock_products.keys())),

            # Combined totals
            'total_low_stock_items': len(low_stock_ingredients) + len(low_stock_product_items),
            'total_critical_items': len(out_of_stock_product_items),
            'has_any_alerts': len(low_stock_ingredients) > 0 or len(low_stock_product_items) > 0 or len(out_of_stock_product_items) > 0
        }

    @staticmethod
    def get_product_stock_summary() -> Dict:
        """Purpose: Provide backward-compatible product alert payloads from the unified summary."""
        unified_summary = CombinedInventoryAlertService.get_unified_stock_summary()

        # Return only product-related data for compatibility
        return {
            'low_stock_skus': unified_summary['low_stock_skus'],
            'out_of_stock_skus': unified_summary['out_of_stock_skus'],
            'low_stock_products': unified_summary['low_stock_products'],
            'out_of_stock_products': unified_summary['out_of_stock_products'],
            'low_stock_count': unified_summary['low_stock_count'],
            'out_of_stock_count': unified_summary['out_of_stock_count'],
            'affected_products_count': unified_summary['affected_products_count']
        }