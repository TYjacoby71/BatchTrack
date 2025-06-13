
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from models import db, InventoryItem, Batch, ProductInventory, Timer
from services.inventory_alerts import get_low_stock_ingredients
from blueprints.expiration.services import ExpirationService
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
        
        # CRITICAL: Stuck batches (in progress > 24 hours)
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
        
        # CRITICAL: Recent fault log errors
        recent_faults = DashboardAlertService._get_recent_faults()
        if recent_faults:
            alerts.append({
                'priority': 'CRITICAL',
                'type': 'fault_errors',
                'title': 'System Faults',
                'message': f"{recent_faults} critical faults in last 24 hours",
                'action_url': '/faults/view_fault_log',
                'action_text': 'View Faults',
                'dismissible': False
            })
        
        # HIGH: Expired/expiring timers
        timer_alerts = DashboardAlertService._get_timer_alerts()
        if timer_alerts['expired_count'] > 0:
            alerts.append({
                'priority': 'HIGH',
                'type': 'expired_timers',
                'title': 'Timer Alert',
                'message': f"{timer_alerts['expired_count']} timers have expired",
                'action_url': '/timers/list_timers',
                'action_text': 'Check Timers',
                'dismissible': True
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
        
        # HIGH: Product inventory issues
        product_issues = DashboardAlertService._get_product_inventory_issues()
        if product_issues:
            alerts.append({
                'priority': 'HIGH',
                'type': 'product_issues',
                'title': 'Product Stock Issues',
                'message': f"{product_issues} products have inventory issues",
                'action_url': '/products/product_list',
                'action_text': 'Review Products',
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
        low_stock_count = len(get_low_stock_ingredients())
        stuck_batches = len(DashboardAlertService._get_stuck_batches())
        recent_faults = DashboardAlertService._get_recent_faults()
        timer_alerts = DashboardAlertService._get_timer_alerts()
        
        critical_count = summary['expired_total'] + stuck_batches + (1 if recent_faults > 0 else 0)
        high_count = (summary['expiring_soon_total'] + low_stock_count + 
                     timer_alerts['expired_count'] + 
                     DashboardAlertService._get_product_inventory_issues())
        
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
            # Check if Timer model exists and get expired timers
            active_timers = Timer.query.filter_by(is_active=True).all()
            expired_count = 0
            
            for timer in active_timers:
                if hasattr(timer, 'end_time') and timer.end_time:
                    if datetime.utcnow() > timer.end_time:
                        expired_count += 1
            
            return {
                'expired_count': expired_count,
                'active_count': len(active_timers)
            }
        except:
            # Timer model might not exist or have different structure
            return {'expired_count': 0, 'active_count': 0}
    
    @staticmethod
    def _get_product_inventory_issues() -> int:
        """Get count of products with inventory issues"""
        try:
            # Products with zero or negative inventory
            issues = ProductInventory.query.filter(
                ProductInventory.quantity <= 0
            ).count()
            return issues
        except:
            return 0
    
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
