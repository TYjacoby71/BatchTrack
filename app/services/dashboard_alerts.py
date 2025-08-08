from typing import Dict, List, Optional
from datetime import datetime, timedelta
from flask_login import current_user
from ..models import db, InventoryItem, Batch, ProductSKU, UserPreferences
from ..services.combined_inventory_alerts import CombinedInventoryAlertService
from ..blueprints.expiration.services import ExpirationService
import json
import os

class DashboardAlertsService:
    """Service for managing dashboard alerts and notifications"""

    @staticmethod
    def get_dashboard_alerts() -> Dict:
        """Get all dashboard alerts for the current user"""
        if not current_user or not current_user.is_authenticated:
            return {
                'critical': [],
                'high': [],
                'medium': [],
                'low': [],
                'stats': {'total': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            }

        # Get user preferences for alert filtering
        user_prefs = None
        if current_user.organization_id:
            user_prefs = UserPreferences.query.filter_by(
                user_id=current_user.id,
                organization_id=current_user.organization_id
            ).first()

        alerts = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }

        # CRITICAL: Items with zero or negative stock
        try:
            critical_stock_issues = DashboardAlertsService._get_critical_stock_issues()
            if critical_stock_issues > 0:
                alerts['critical'].append({
                    'type': 'critical_stock',
                    'title': 'Critical Stock Issues',
                    'message': f'{critical_stock_issues} items have zero or negative stock',
                    'count': critical_stock_issues,
                    'action_url': '/inventory',
                    'icon': 'exclamation-triangle'
                })
        except Exception as e:
            print(f"Error getting critical stock issues: {e}")

        # HIGH: Expiring items (next 7 days)
        try:
            expiring_soon = DashboardAlertsService._get_expiring_items_count(days=7)
            if expiring_soon > 0:
                alerts['high'].append({
                    'type': 'expiring_soon',
                    'title': 'Items Expiring Soon',
                    'message': f'{expiring_soon} items expire within 7 days',
                    'count': expiring_soon,
                    'action_url': '/expiration/alerts',
                    'icon': 'clock'
                })
        except Exception as e:
            print(f"Error getting expiring items: {e}")

        # MEDIUM: Active batches needing attention - only if enabled
        if user_prefs and user_prefs.show_batch_alerts:
            if current_user and current_user.is_authenticated and current_user.organization_id:
                active_batches = Batch.query.filter_by(
                    status='in_progress',
                    organization_id=current_user.organization_id
                ).count()
            else:
                active_batches = 0

            if active_batches > 0:
                alerts['medium'].append({
                    'type': 'active_batches',
                    'title': 'Active Batches',
                    'message': f'{active_batches} batches in progress',
                    'count': active_batches,
                    'action_url': '/batches',
                    'icon': 'play-circle'
                })

        # MEDIUM: Long-running batches (>24 hours)
        try:
            long_running_batches = DashboardAlertsService._get_long_running_batches()
            if long_running_batches > 0:
                alerts['medium'].append({
                    'type': 'long_running_batches',
                    'title': 'Long-Running Batches',
                    'message': f'{long_running_batches} batches running over 24 hours',
                    'count': long_running_batches,
                    'action_url': '/batches',
                    'icon': 'hourglass'
                })
        except Exception as e:
            print(f"Error getting long-running batches: {e}")

        # LOW: Active timers
        try:
            active_timers = DashboardAlertsService._get_active_timers_count()
            if active_timers > 0:
                alerts['low'].append({
                    'type': 'active_timers',
                    'title': 'Active Timers',
                    'message': f'{active_timers} timers currently running',
                    'count': active_timers,
                    'action_url': '/timers',
                    'icon': 'stopwatch'
                })
        except Exception as e:
            print(f"Error getting active timers: {e}")

        # Calculate stats
        stats = {
            'critical': len(alerts['critical']),
            'high': len(alerts['high']),
            'medium': len(alerts['medium']),
            'low': len(alerts['low'])
        }
        stats['total'] = stats['critical'] + stats['high'] + stats['medium'] + stats['low']

        return {
            'critical': alerts['critical'],
            'high': alerts['high'],
            'medium': alerts['medium'],
            'low': alerts['low'],
            'stats': stats
        }

    @staticmethod
    def _get_expiring_items_count(days: int = 7) -> int:
        """Get count of items expiring within specified days"""
        try:
            from ..blueprints.expiration.services import ExpirationService

            if current_user and current_user.is_authenticated and current_user.organization_id:
                return ExpirationService.get_expiring_items_count(
                    organization_id=current_user.organization_id,
                    days_ahead=days
                )
            return 0
        except:
            return 0

    @staticmethod
    def _get_long_running_batches() -> int:
        """Get count of batches running longer than 24 hours"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            query = Batch.query.filter(
                Batch.status == 'in_progress',
                Batch.started_at < cutoff_time
            )

            # Simple organization scoping - no complex developer logic here
            if current_user and current_user.is_authenticated and current_user.organization_id:
                query = query.filter(Batch.organization_id == current_user.organization_id)

            return query.count()
        except:
            return 0

    @staticmethod
    def _get_active_timers_count() -> int:
        """Get count of active timers"""
        try:
            from ..models import BatchTimer
            from ..utils.timezone_utils import TimezoneUtils

            # Get active timers with simple organization scoping
            query = BatchTimer.query.filter_by(status='active')

            if current_user and current_user.is_authenticated and current_user.organization_id:
                query = query.filter(BatchTimer.organization_id == current_user.organization_id)

            return query.count()
        except:
            return 0

    @staticmethod
    def _get_critical_stock_issues() -> int:
        """Get count of items with critical stock issues"""
        try:
            from ..models.product import ProductSKU

            # SKUs with zero or negative inventory - simple organization scoping
            query = ProductSKU.query.filter(ProductSKU.current_quantity <= 0)

            if current_user and current_user.is_authenticated and current_user.organization_id:
                query = query.filter(ProductSKU.organization_id == current_user.organization_id)

            issues = query.count()
            return issues
        except:
            return 0

    @staticmethod
    def _get_incomplete_batches() -> int:
        """Get count of completed batches missing final data"""
        try:
            query = Batch.query.filter(
                Batch.status == 'completed',
                Batch.final_yield.is_(None)
            )

            # Simple organization scoping
            if current_user and current_user.is_authenticated and current_user.organization_id:
                query = query.filter(Batch.organization_id == current_user.organization_id)

            return query.count()
        except:
            return 0

    @staticmethod
    def dismiss_alert(alert_type: str, alert_id: Optional[str] = None) -> bool:
        """Dismiss a specific alert"""
        try:
            # Implementation for dismissing alerts
            # This could store dismissed alerts in user preferences
            return True
        except:
            return False

    @staticmethod
    def get_alert_preferences() -> Dict:
        """Get user's alert preferences"""
        if not current_user or not current_user.is_authenticated:
            return {}

        try:
            user_prefs = UserPreferences.query.filter_by(
                user_id=current_user.id,
                organization_id=current_user.organization_id
            ).first()

            if user_prefs:
                return {
                    'show_stock_alerts': getattr(user_prefs, 'show_stock_alerts', True),
                    'show_expiration_alerts': getattr(user_prefs, 'show_expiration_alerts', True),
                    'show_batch_alerts': getattr(user_prefs, 'show_batch_alerts', True),
                    'show_timer_alerts': getattr(user_prefs, 'show_timer_alerts', True)
                }
        except:
            pass

        return {
            'show_stock_alerts': True,
            'show_expiration_alerts': True,
            'show_batch_alerts': True,
            'show_timer_alerts': True
        }