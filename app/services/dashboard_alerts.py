from .base_service import CacheableService
from typing import List, Dict, Any, Optional
from app.models import Batch, InventoryItem, Product
from flask_login import current_user
from datetime import datetime, timedelta
import logging

class DashboardAlertService(CacheableService):
    """Consolidated dashboard alert service with cognitive load management"""

    def __init__(self):
        super().__init__()
        self.max_alerts_default = 5

    def get_dashboard_alerts(self, organization_id: Optional[int] = None, 
                           max_alerts: Optional[int] = None, 
                           dismissed_alerts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get prioritized dashboard alerts for organization"""
        if not organization_id:
            organization_id = current_user.organization_id

        if not self.validate_organization_access(organization_id, current_user.id):
            return {'alerts': [], 'total_alerts': 0, 'hidden_count': 0}

        cache_key = f"dashboard_alerts_{organization_id}"
        dismissed_alerts = dismissed_alerts or []
        max_alerts = max_alerts or self.max_alerts_default

        def fetch_alerts():
            all_alerts = []

            # Get all alert types
            all_alerts.extend(self._get_expiration_alerts(organization_id))
            all_alerts.extend(self._get_inventory_alerts(organization_id))
            all_alerts.extend(self._get_batch_alerts(organization_id))
            all_alerts.extend(self._get_product_alerts(organization_id))
            all_alerts.extend(self._get_timer_alerts(organization_id))

            # Filter dismissed alerts
            filtered_alerts = [alert for alert in all_alerts 
                             if alert['type'] not in dismissed_alerts]

            # Sort by priority and timestamp
            priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            filtered_alerts.sort(key=lambda x: (
                priority_order.get(x.get('priority', 'LOW'), 3),
                x.get('timestamp', datetime.min)
            ))

            # Apply cognitive load management
            visible_alerts = filtered_alerts[:max_alerts]
            hidden_count = len(filtered_alerts) - len(visible_alerts)

            return {
                'alerts': visible_alerts,
                'total_alerts': len(all_alerts),
                'hidden_count': hidden_count
            }

        return self.get_cached(cache_key, fetch_alerts, ttl=300)

    def _get_expiration_alerts(self, organization_id: int) -> List[Dict]:
        """Get expiration alerts"""
        thirty_days = datetime.utcnow() + timedelta(days=30)

        expiring_inventory = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.expiration_date <= thirty_days,
            InventoryItem.quantity > 0
        ).all()

        alerts = []
        for item in expiring_inventory:
            days_until = (item.expiration_date - datetime.utcnow()).days
            severity = 'CRITICAL' if days_until <= 3 else 'HIGH' if days_until <= 7 else 'MEDIUM'

            alerts.append({
                'type': 'expiration',
                'priority': severity,
                'title': f'Ingredient Expiring Soon',
                'message': f"{item.ingredient.name} expires in {days_until} days",
                'action_url': f'/inventory/view/{item.id}',
                'action_text': 'View Details',
                'dismissible': True,
                'timestamp': datetime.utcnow(),
                'item_id': item.id,
                'days_until': days_until
            })

        return alerts

    def _get_inventory_alerts(self, organization_id: int) -> List[Dict]:
        """Get low inventory alerts"""
        low_stock = InventoryItem.query.filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.quantity <= InventoryItem.minimum_stock_level,
            InventoryItem.quantity > 0
        ).all()

        alerts = []
        for item in low_stock:
            shortage_pct = (item.quantity / item.minimum_stock_level) * 100
            severity = 'HIGH' if shortage_pct <= 25 else 'MEDIUM'

            alerts.append({
                'type': 'low_stock',
                'priority': severity,
                'title': 'Low Stock Alert',
                'message': f"{item.ingredient.name} is running low ({item.quantity} {item.unit.symbol} remaining)",
                'action_url': f'/inventory/view/{item.id}',
                'action_text': 'Restock',
                'dismissible': True,
                'timestamp': datetime.utcnow(),
                'item_id': item.id,
                'current_quantity': item.quantity,
                'minimum_level': item.minimum_stock_level
            })

        return alerts

    def _get_batch_alerts(self, organization_id: int) -> List[Dict]:
        """Get batch-related alerts"""
        alerts = []

        # Long running batches
        long_running = Batch.query.filter(
            Batch.organization_id == organization_id,
            Batch.status == 'in_progress',
            Batch.started_at <= datetime.utcnow() - timedelta(hours=24)
        ).all()

        for batch in long_running:
            hours_running = (datetime.utcnow() - batch.started_at).total_seconds() / 3600
            alerts.append({
                'type': 'long_running_batch',
                'priority': 'MEDIUM',
                'title': 'Long Running Batch',
                'message': f"Batch #{batch.batch_number} has been running for {hours_running:.1f} hours",
                'action_url': f'/batches/view/{batch.id}',
                'action_text': 'View Batch',
                'dismissible': True,
                'timestamp': datetime.utcnow(),
                'batch_id': batch.id,
                'hours_running': hours_running
            })

        # Incomplete batches (older than 7 days)
        incomplete = Batch.query.filter(
            Batch.organization_id == organization_id,
            Batch.status == 'planning',
            Batch.created_at <= datetime.utcnow() - timedelta(days=7)
        ).all()

        for batch in incomplete:
            alerts.append({
                'type': 'incomplete_batch',
                'priority': 'LOW',
                'title': 'Incomplete Batch',
                'message': f"Batch #{batch.batch_number} has been in planning for over a week",
                'action_url': f'/batches/view/{batch.id}',
                'action_text': 'Complete Planning',
                'dismissible': True,
                'timestamp': datetime.utcnow(),
                'batch_id': batch.id
            })

        return alerts

    def _get_product_alerts(self, organization_id: int) -> List[Dict]:
        """Get product-related alerts"""
        low_stock_products = Product.query.filter(
            Product.organization_id == organization_id,
            Product.current_inventory <= Product.minimum_stock_level
        ).all()

        alerts = []
        for product in low_stock_products:
            alerts.append({
                'type': 'product_low_stock',
                'priority': 'MEDIUM',
                'title': 'Product Low Stock',
                'message': f"Product '{product.name}' is running low",
                'action_url': f'/products/view/{product.id}',
                'action_text': 'View Product',
                'dismissible': True,
                'timestamp': datetime.utcnow(),
                'product_id': product.id,
                'current_stock': product.current_inventory,
                'minimum_level': product.minimum_stock_level
            })

        return alerts

    def _get_timer_alerts(self, organization_id: int) -> List[Dict]:
        """Get timer-related alerts (placeholder for future timer functionality)"""
        # This would integrate with timer service when implemented
        return []

    def clear_organization_cache(self, organization_id: int):
        """Clear all cached alerts for an organization"""
        self.clear_cache(f"dashboard_alerts_{organization_id}")
        self.log_operation("clear_alerts_cache", {"organization_id": organization_id})

# Service instance
dashboard_alert_service = DashboardAlertService()