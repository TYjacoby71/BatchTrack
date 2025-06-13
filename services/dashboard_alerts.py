
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from models import db, InventoryItem, Batch
from services.inventory_alerts import get_low_stock_ingredients
from blueprints.expiration.services import ExpirationService
import json

class DashboardAlertService:
    """Unified alert management for neurodivergent-friendly dashboard"""
    
    PRIORITY_LEVELS = {
        'CRITICAL': 1,    # Requires immediate action
        'HIGH': 2,        # Should be addressed today
        'MEDIUM': 3,      # Should be addressed this week
        'LOW': 4          # Informational
    }
    
    @staticmethod
    def get_dashboard_alerts(max_alerts: int = 3) -> Dict:
        """Get prioritized alerts for dashboard with cognitive load management"""
        alerts = []
        
        # CRITICAL: Expired items with remaining quantity
        expired_data = ExpirationService.get_expired_inventory_items()
        if expired_data['fifo_entries'] or expired_data['product_inventory']:
            expired_count = len(expired_data['fifo_entries']) + len(expired_data['product_inventory'])
            alerts.append({
                'priority': 'CRITICAL',
                'type': 'expiration',
                'title': 'Expired Inventory',
                'message': f"{expired_count} items have expired and need attention",
                'action_url': '/expiration/alerts',
                'action_text': 'Review Expired Items',
                'dismissible': False
            })
        
        # HIGH: Low stock items
        low_stock = get_low_stock_ingredients()
        if low_stock:
            alerts.append({
                'priority': 'HIGH',
                'type': 'low_stock',
                'title': 'Low Stock Warning',
                'message': f"{len(low_stock)} ingredients are running low",
                'action_url': '/inventory/',
                'action_text': 'View Inventory',
                'dismissible': True
            })
        
        # HIGH: Items expiring soon
        expiring_data = ExpirationService.get_expiring_soon_items(3)  # 3 days
        expiring_count = len(expiring_data['fifo_entries']) + len(expiring_data['product_inventory'])
        if expiring_count > 0:
            alerts.append({
                'priority': 'HIGH',
                'type': 'expiring_soon',
                'title': 'Expiring Soon',
                'message': f"{expiring_count} items expire within 3 days",
                'action_url': '/expiration/alerts',
                'action_text': 'Plan Usage',
                'dismissible': True
            })
        
        # MEDIUM: Active batches needing attention
        active_batches = Batch.query.filter_by(status='in_progress').count()
        if active_batches > 0:
            alerts.append({
                'priority': 'MEDIUM',
                'type': 'active_batches',
                'title': 'Active Batches',
                'message': f"{active_batches} batches in progress",
                'action_url': '/batches/',
                'action_text': 'View Batches',
                'dismissible': True
            })
        
        # Sort by priority and limit
        alerts.sort(key=lambda x: DashboardAlertService.PRIORITY_LEVELS[x['priority']])
        return {
            'alerts': alerts[:max_alerts],
            'total_alerts': len(alerts),
            'hidden_count': max(0, len(alerts) - max_alerts)
        }
    
    @staticmethod
    def get_alert_summary() -> Dict:
        """Get summary counts for navigation badge"""
        summary = ExpirationService.get_expiration_summary()
        low_stock_count = len(get_low_stock_ingredients())
        
        return {
            'critical_count': summary['expired_total'],
            'high_count': summary['expiring_soon_total'] + low_stock_count,
            'total_count': summary['expired_total'] + summary['expiring_soon_total'] + low_stock_count
        }
