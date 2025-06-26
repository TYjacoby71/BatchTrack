
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..models import db, InventoryItem, Batch, ProductSKU
from ..services.inventory_alerts import get_low_stock_ingredients
from ..services.product_alerts import ProductAlertService
from ..blueprints.expiration.services import ExpirationService
import json
import os

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
        
        # Get expiration summary once
        expiration_summary = ExpirationService.get_expiration_summary()
        
        # CRITICAL: Expired items with remaining quantity
        if expiration_summary['expired_total'] > 0:
            alerts.append({
                'priority': 'CRITICAL',
                'type': 'expired_inventory',
                'title': 'Expired Inventory',
                'message': f"{expiration_summary['expired_total']} items have expired and need attention",
                'action_url': '/expiration/alerts',
                'action_text': 'Review Expired Items',
                'dismissible': False
            })
        
        # CRITICAL: Stuck batches (in progress > 24 hours) - only if enabled in settings
        if DashboardAlertService._is_alert_enabled('show_batch_alerts'):
            stuck_batches = DashboardAlertService._get_stuck_batches()
            if stuck_batches:
                alerts.append({
                    'priority': 'CRITICAL',
                    'type': 'stuck_batches',
                    'title': 'Stuck Batches',
                    'message': f"{len(stuck_batches)} batches may be stuck",
                    'action_url': '/batches/',
                    'action_text': 'Review Batches',
                    'dismissible': False
                })
        
        # CRITICAL: Recent fault log errors - only if enabled
        if DashboardAlertService._is_alert_enabled('show_fault_alerts'):
            recent_faults = DashboardAlertService._get_recent_faults()
            if recent_faults > 0:
                alerts.append({
                    'priority': 'CRITICAL',
                    'type': 'fault_errors',
                    'title': 'System Faults',
                    'message': f"{recent_faults} critical faults in last 24 hours",
                    'action_url': '/faults/view_fault_log',
                    'action_text': 'View Faults',
                    'dismissible': False
                })
        
        # HIGH: Items expiring soon (within 3 days) - only if enabled
        if DashboardAlertService._is_alert_enabled('show_expiration_alerts') and expiration_summary['expiring_soon_total'] > 0:
            alerts.append({
                'priority': 'HIGH',
                'type': 'expiring_soon',
                'title': 'Expiring Soon',
                'message': f"{expiration_summary['expiring_soon_total']} items expire within 3 days",
                'action_url': '/expiration/alerts',
                'action_text': 'Plan Usage',
                'dismissible': True
            })
        
        # HIGH: Low stock items - only if enabled
        if DashboardAlertService._is_alert_enabled('show_low_stock_alerts'):
            low_stock_ingredients = get_low_stock_ingredients()
            product_stock_summary = ProductAlertService.get_product_stock_summary()
            
            if low_stock_ingredients:
                alerts.append({
                    'priority': 'HIGH',
                    'type': 'low_stock_ingredients',
                    'title': 'Low Stock Ingredients',
                    'message': f"{len(low_stock_ingredients)} ingredients are running low",
                    'action_url': '/inventory/',
                    'action_text': 'View Inventory',
                    'dismissible': True
                })
            
            if product_stock_summary['low_stock_count'] > 0:
                alerts.append({
                    'priority': 'HIGH',
                    'type': 'low_stock_products',
                    'title': 'Low Stock Products',
                    'message': f"{product_stock_summary['affected_products_count']} products have low stock SKUs",
                    'action_url': '/products/',
                    'action_text': 'View Products',
                    'dismissible': True
                })
            
            if product_stock_summary['out_of_stock_count'] > 0:
                alerts.append({
                    'priority': 'CRITICAL',
                    'type': 'out_of_stock_products',
                    'title': 'Out of Stock Products',
                    'message': f"{product_stock_summary['out_of_stock_count']} product SKUs are out of stock",
                    'action_url': '/products/',
                    'action_text': 'View Products',
                    'dismissible': False
                })
        
        # HIGH: Expired timers - only if enabled
        if DashboardAlertService._is_alert_enabled('show_timer_alerts'):
            timer_alerts = DashboardAlertService._get_timer_alerts()
            if timer_alerts['expired_count'] > 0:
                # Get the first expired timer's batch for redirection
                batch_url = '/batches/'
                if timer_alerts['expired_timers']:
                    first_timer = timer_alerts['expired_timers'][0]
                    if hasattr(first_timer, 'batch_id') and first_timer.batch_id:
                        batch_url = f'/batches/in-progress/{first_timer.batch_id}'
                
                alerts.append({
                    'priority': 'HIGH',
                    'type': 'expired_timers',
                    'title': 'Timer Alert',
                    'message': f"{timer_alerts['expired_count']} timers have expired",
                    'action_url': batch_url,
                    'action_text': 'View Batch',
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
        
        # MEDIUM: Incomplete batches
        incomplete_batches = DashboardAlertService._get_incomplete_batches()
        if incomplete_batches:
            alerts.append({
                'priority': 'MEDIUM',
                'type': 'incomplete_batches',
                'title': 'Incomplete Batches',
                'message': f"{incomplete_batches} batches need completion",
                'action_url': '/batches/',
                'action_text': 'Complete Batches',
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
        low_stock_ingredients = len(get_low_stock_ingredients())
        product_stock_summary = ProductAlertService.get_product_stock_summary()
        stuck_batches = len(DashboardAlertService._get_stuck_batches())
        recent_faults = DashboardAlertService._get_recent_faults()
        timer_alerts = DashboardAlertService._get_timer_alerts()
        
        critical_count = (summary['expired_total'] + stuck_batches + 
                         (1 if recent_faults > 0 else 0) + 
                         product_stock_summary['out_of_stock_count'])
        high_count = (summary['expiring_soon_total'] + low_stock_ingredients + 
                     timer_alerts['expired_count'] + 
                     product_stock_summary['low_stock_count'])
        
        return {
            'critical_count': critical_count,
            'high_count': high_count,
            'total_count': critical_count + high_count
        }
    
    @staticmethod
    def _get_stuck_batches() -> List:
        """Get batches that have been in progress for more than 24 hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        return Batch.query.filter(
            Batch.status == 'in_progress',
            Batch.started_at < cutoff_time
        ).all()
    
    @staticmethod
    def _get_recent_faults() -> int:
        """Get count of recent critical faults"""
        fault_file = 'faults.json'
        if not os.path.exists(fault_file):
            return 0
        
        try:
            with open(fault_file, 'r') as f:
                faults = json.load(f)
            
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            recent_critical = 0
            
            for fault in faults:
                fault_time = datetime.fromisoformat(fault.get('timestamp', ''))
                if (fault_time > cutoff_time and 
                    fault.get('severity', '').lower() in ['critical', 'error']):
                    recent_critical += 1
            
            return recent_critical
        except (json.JSONDecodeError, KeyError, ValueError):
            return 0
    
    @staticmethod
    def _get_timer_alerts() -> Dict:
        """Get timer-related alerts"""
        try:
            # Use BatchTimer model which exists in your system
            from models import BatchTimer
            active_timers = BatchTimer.query.filter_by(status='active').all()
            expired_timers = []
            
            for timer in active_timers:
                if timer.start_time and timer.duration_seconds:
                    end_time = timer.start_time + timedelta(seconds=timer.duration_seconds)
                    if datetime.utcnow() > end_time:
                        expired_timers.append(timer)
            
            return {
                'expired_count': len(expired_timers),
                'expired_timers': expired_timers,
                'active_count': len(active_timers)
            }
        except (ImportError, AttributeError):
            # Fallback if BatchTimer doesn't exist
            return {'expired_count': 0, 'expired_timers': [], 'active_count': 0}
    
    @staticmethod
    def _get_product_inventory_issues() -> int:
        """Get count of products with inventory issues"""
        try:
            # SKUs with zero or negative inventory
            issues = ProductSKU.query.filter(
                ProductSKU.current_quantity <= 0
            ).count()
            return issues
        except:
            return 0
    
    @staticmethod
    def _is_alert_enabled(alert_type: str) -> bool:
        """Check if a specific alert type is enabled in settings"""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                return settings.get('alerts', {}).get(alert_type, True)  # Default to True if not set
        except (FileNotFoundError, json.JSONDecodeError):
            return True  # Default to enabled if settings can't be read
    
    @staticmethod
    def _get_incomplete_batches() -> int:
        """Get count of batches missing required data"""
        try:
            # Batches that are finished but missing containers or labels
            incomplete = Batch.query.filter(
                Batch.status == 'finished',
                Batch.final_yield.is_(None)
            ).count()
            return incomplete
        except:
            return 0
