
"""
Dashboard Alerts Service
Provides dashboard alert functionality for the application.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from flask_login import current_user
from app.models import InventoryItem, Batch, ProductSKU
from app.utils.timezone_utils import TimezoneUtils
from .base_service import CacheableService


class DashboardAlertService(CacheableService):
    """Service for generating dashboard alerts using proper base service architecture"""
    
    def get_dashboard_alerts(self, organization_id: int, max_alerts: int = None, dismissed_alerts: List[str] = None) -> Dict[str, Any]:
        """Get all dashboard alerts for an organization"""
        if not self.validate_organization_access(organization_id, current_user.id):
            return self.handle_service_error(
                Exception("Access denied to organization"), 
                "get_dashboard_alerts"
            )
        
        cache_key = f"dashboard_alerts_{organization_id}"
        
        try:
            alerts_data = self.get_cached(cache_key, lambda: self._fetch_all_alerts(organization_id), ttl=300)
            
            # Filter out dismissed alerts
            if dismissed_alerts:
                alerts_data = [alert for alert in alerts_data if alert.get('type') not in dismissed_alerts]
            
            # Apply max_alerts limit
            if max_alerts and len(alerts_data) > max_alerts:
                visible_alerts = alerts_data[:max_alerts]
                hidden_count = len(alerts_data) - max_alerts
            else:
                visible_alerts = alerts_data
                hidden_count = 0
            
            self.log_operation("get_dashboard_alerts", {
                'organization_id': organization_id,
                'total_alerts': len(alerts_data),
                'visible_alerts': len(visible_alerts),
                'hidden_count': hidden_count
            }, current_user.id)
            
            return {
                'success': True,
                'alerts': visible_alerts,
                'total_alerts': len(alerts_data),
                'hidden_count': hidden_count
            }
            
        except Exception as e:
            return self.handle_service_error(e, "get_dashboard_alerts")
    
    def _fetch_all_alerts(self, organization_id: int) -> List[Dict[str, Any]]:
        """Fetch all alerts for organization"""
        alerts = []
        
        # Get different types of alerts
        alerts.extend(self._get_low_stock_alerts(organization_id))
        alerts.extend(self._get_expiring_inventory_alerts(organization_id))
        alerts.extend(self._get_active_batch_alerts(organization_id))
        
        # Sort by priority/severity
        priority_order = {'critical': 0, 'danger': 1, 'warning': 2, 'info': 3}
        alerts.sort(key=lambda x: priority_order.get(x.get('severity', 'info'), 3))
        
        return alerts
    
    def _get_low_stock_alerts(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get low stock alerts"""
        alerts = []
        
        try:
            # Get inventory items with low stock
            low_stock_items = InventoryItem.query.filter(
                InventoryItem.organization_id == organization_id,
                InventoryItem.current_quantity <= InventoryItem.min_stock_level,
                InventoryItem.min_stock_level > 0
            ).all()
            
            for item in low_stock_items:
                alerts.append({
                    'type': 'low_stock',
                    'severity': 'warning',
                    'title': f'Low Stock: {item.name}',
                    'message': f'Only {item.current_quantity} {item.unit.symbol if item.unit else ""} remaining',
                    'item_id': item.id,
                    'timestamp': TimezoneUtils.utc_now(),
                    'dismissible': True,
                    'priority': 'HIGH'
                })
        except Exception as e:
            self.logger.error(f"Error fetching low stock alerts: {e}")
            
        return alerts
    
    def _get_expiring_inventory_alerts(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get expiring inventory alerts"""
        alerts = []
        
        try:
            # Get items expiring in next 7 days
            cutoff_date = TimezoneUtils.utc_now() + timedelta(days=7)
            
            expiring_items = InventoryItem.query.filter(
                InventoryItem.organization_id == organization_id,
                InventoryItem.expiration_date.isnot(None),
                InventoryItem.expiration_date <= cutoff_date,
                InventoryItem.current_quantity > 0
            ).all()
            
            for item in expiring_items:
                days_until = (item.expiration_date - TimezoneUtils.utc_now().date()).days
                severity = 'danger' if days_until <= 3 else 'warning'
                
                alerts.append({
                    'type': 'expiring',
                    'severity': severity,
                    'title': f'Expiring Soon: {item.name}',
                    'message': f'Expires on {item.expiration_date.strftime("%Y-%m-%d")} ({days_until} days)',
                    'item_id': item.id,
                    'timestamp': TimezoneUtils.utc_now(),
                    'dismissible': True,
                    'priority': 'CRITICAL' if days_until <= 1 else 'HIGH'
                })
        except Exception as e:
            self.logger.error(f"Error fetching expiring inventory alerts: {e}")
            
        return alerts
    
    def _get_active_batch_alerts(self, organization_id: int) -> List[Dict[str, Any]]:
        """Get active batch alerts"""
        alerts = []
        
        try:
            # Get batches in progress for more than 24 hours
            cutoff_time = TimezoneUtils.utc_now() - timedelta(hours=24)
            
            long_running_batches = Batch.query.filter(
                Batch.organization_id == organization_id,
                Batch.status == 'in_progress',
                Batch.started_at <= cutoff_time
            ).all()
            
            for batch in long_running_batches:
                hours_running = (TimezoneUtils.utc_now() - batch.started_at).total_seconds() / 3600
                
                alerts.append({
                    'type': 'long_batch',
                    'severity': 'info',
                    'title': f'Long Running Batch: {batch.batch_number}',
                    'message': f'Started {batch.started_at.strftime("%Y-%m-%d %H:%M")} ({int(hours_running)}h ago)',
                    'batch_id': batch.id,
                    'timestamp': TimezoneUtils.utc_now(),
                    'dismissible': True,
                    'priority': 'MEDIUM',
                    'action_url': f'/batches/{batch.id}',
                    'action_text': 'View Batch'
                })
        except Exception as e:
            self.logger.error(f"Error fetching batch alerts: {e}")
            
        return alerts
    
    def clear_organization_cache(self, organization_id: int):
        """Clear all cached alerts for an organization"""
        self.clear_cache(f"dashboard_alerts_{organization_id}")
        self.log_operation("clear_organization_cache", {
            'organization_id': organization_id
        }, current_user.id if current_user.is_authenticated else None)


# Create singleton instance
dashboard_alert_service = DashboardAlertService()
