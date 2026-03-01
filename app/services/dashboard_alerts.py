import logging
# Import moved to avoid circular dependency
# from ..blueprints.expiration.services import ExpirationService
import os
from datetime import datetime, timedelta
from typing import Dict, List

from flask_login import current_user

from ..models import Batch, UserPreferences
from ..services.combined_inventory_alerts import CombinedInventoryAlertService
from ..utils.json_store import read_json_file

logger = logging.getLogger(__name__)



class DashboardAlertService:
    """Unified alert management for neurodivergent-friendly dashboard"""

    PRIORITY_LEVELS = {
        "CRITICAL": 1,  # Requires immediate action
        "HIGH": 2,  # Should be addressed today
        "MEDIUM": 3,  # Should be addressed this week
        "LOW": 4,  # Informational
    }

    @staticmethod
    def get_dashboard_alerts(
        max_alerts: int = None, dismissed_alerts: list = None
    ) -> Dict:
        """Get prioritized alerts for dashboard with cognitive load management"""

        # Get user preferences
        user_prefs = None
        if current_user and current_user.is_authenticated:
            user_prefs = UserPreferences.get_for_user(current_user.id)
            if user_prefs and max_alerts is None:
                max_alerts = user_prefs.max_dashboard_alerts

        if max_alerts is None:
            max_alerts = 3  # Default fallback

        # Get expiration data from combined service
        from ..utils.settings import get_setting

        expiration_days = get_setting("alerts.expiration_warning_days", 7)
        expiration_data = CombinedInventoryAlertService.get_expiration_alerts(
            days_ahead=expiration_days
        )

        # CRITICAL: Expired items with remaining quantity - only if enabled (default to True if no prefs)
        show_expiration = user_prefs.show_expiration_alerts if user_prefs else True

        # Get stuck batches and faults
        stuck_batches_count = len(DashboardAlertService._get_stuck_batches())
        recent_faults = DashboardAlertService._get_recent_faults()

        # Get stock summary
        stock_summary = CombinedInventoryAlertService.get_unified_stock_summary()
        low_stock_ingredients_count = stock_summary.get(
            "low_stock_ingredients_count", 0
        )
        low_stock_count = stock_summary.get("low_stock_count", 0)
        out_of_stock_count = stock_summary.get("out_of_stock_count", 0)

        # Get timer alerts
        timer_alerts = DashboardAlertService._get_timer_alerts()

        # Get incomplete batches
        incomplete_batches_count = DashboardAlertService._get_incomplete_batches()

        # Initialize alert counts
        expired_total = expiration_data.get("expired_total", 0)
        expiring_soon_total = expiration_data.get("expiring_soon_total", 0)

        # Define alert preference flags
        show_batch_alerts = user_prefs.show_batch_alerts if user_prefs else True
        show_fault_alerts = user_prefs.show_fault_alerts if user_prefs else True
        show_low_stock = user_prefs.show_low_stock_alerts if user_prefs else True
        show_timer_alerts = user_prefs.show_timer_alerts if user_prefs else True

        if not show_expiration:
            expired_total = 0
            expiring_soon_total = 0

        # Build final alerts list
        alerts = []

        # 1. Expired inventory alert (if enabled and not dismissed)
        if expired_total > 0 and "expired_inventory" not in dismissed_alerts:
            alerts.append(
                {
                    "priority": "CRITICAL",
                    "type": "expired_inventory",
                    "title": "Expired Inventory",
                    "message": f"{expired_total} items have expired and need attention",
                    "action_url": "/expiration/alerts",
                    "action_text": "Review Expired Items",
                    "dismissible": True,
                }
            )

        # CRITICAL: Stuck batches (in progress > 24 hours) - only if enabled in user preferences (default to True)
        if show_batch_alerts and stuck_batches_count > 0:
            alerts.append(
                {
                    "priority": "CRITICAL",
                    "type": "stuck_batches",
                    "title": "Stuck Batches",
                    "message": f"{stuck_batches_count} batches may be stuck",
                    "action_url": "/batches/",
                    "action_text": "Review Batches",
                    "dismissible": True,
                }
            )

        # CRITICAL: Recent fault log errors - only if enabled (default to True)
        if show_fault_alerts and recent_faults > 0:
            alerts.append(
                {
                    "priority": "CRITICAL",
                    "type": "fault_errors",
                    "title": "System Faults",
                    "message": f"{recent_faults} critical faults in last 24 hours",
                    "action_url": "/faults/view_fault_log",
                    "action_text": "View Faults",
                    "dismissible": True,
                }
            )

        # HIGH: Items expiring soon (within expiration_warning_days) - only if enabled (default to True)
        if show_expiration and expiring_soon_total > 0:
            alerts.append(
                {
                    "priority": "HIGH",
                    "type": "expiring_soon",
                    "title": "Expiring Soon",
                    "message": f"{expiring_soon_total} items expire within {expiration_days} days",
                    "action_url": "/expiration/alerts",
                    "action_text": "Plan Usage",
                    "dismissible": True,
                }
            )

        # HIGH: Low stock items - only if enabled (default to True)
        if show_low_stock:
            if low_stock_ingredients_count > 0:
                alerts.append(
                    {
                        "priority": "HIGH",
                        "type": "low_stock_ingredients",
                        "title": "Low Stock Ingredients",
                        "message": f"{low_stock_ingredients_count} ingredients are running low",
                        "action_url": "/inventory/",
                        "action_text": "View Inventory",
                        "dismissible": True,
                    }
                )

            if low_stock_count > 0:
                alerts.append(
                    {
                        "priority": "HIGH",
                        "type": "low_stock_products",
                        "title": "Low Stock Products",
                        "message": f"{stock_summary.get('affected_products_count', 0)} products have low stock SKUs",
                        "action_url": "/products/",
                        "action_text": "View Products",
                        "dismissible": True,
                    }
                )

            if out_of_stock_count > 0:
                alerts.append(
                    {
                        "priority": "CRITICAL",
                        "type": "out_of_stock_products",
                        "title": "Out of Stock Products",
                        "message": f"{out_of_stock_count} product SKUs are out of stock",
                        "action_url": "/products/",
                        "action_text": "View Products",
                        "dismissible": True,
                    }
                )

        # HIGH: Expired timers - only if enabled (default to True)
        if show_timer_alerts and timer_alerts["expired_count"] > 0:
            # Get the first expired timer's batch for redirection
            batch_url = "/batches/"
            if timer_alerts["expired_timers"]:
                first_timer = timer_alerts["expired_timers"][0]
                if hasattr(first_timer, "batch_id") and first_timer.batch_id:
                    batch_url = f"/batches/in-progress/{first_timer.batch_id}"

            alerts.append(
                {
                    "priority": "HIGH",
                    "type": "expired_timers",
                    "title": "Timer Alert",
                    "message": f"{timer_alerts['expired_count']} timers have expired",
                    "action_url": batch_url,
                    "action_text": "View Batch",
                    "dismissible": True,
                }
            )

        # MEDIUM: Active batches needing attention - only if enabled (already set above)
        if show_batch_alerts:
            if (
                current_user
                and current_user.is_authenticated
                and current_user.organization_id
            ):
                active_batches = Batch.query.filter_by(
                    status="in_progress", organization_id=current_user.organization_id
                ).count()
            else:
                active_batches = 0

            if active_batches > 0:
                alerts.append(
                    {
                        "priority": "MEDIUM",
                        "type": "active_batches",
                        "title": "Active Batches",
                        "message": f"{active_batches} batches in progress",
                        "action_url": "/batches/",
                        "action_text": "View Batches",
                        "dismissible": True,
                    }
                )

        # MEDIUM: Incomplete batches
        if incomplete_batches_count > 0:
            alerts.append(
                {
                    "priority": "MEDIUM",
                    "type": "incomplete_batches",
                    "title": "Incomplete Batches",
                    "message": f"{incomplete_batches_count} batches need completion",
                    "action_url": "/batches/",
                    "action_text": "Complete Batches",
                    "dismissible": True,
                }
            )

        # Filter out dismissed alerts from this session
        if dismissed_alerts:
            alerts = [
                alert for alert in alerts if alert["type"] not in dismissed_alerts
            ]

        # Sort by priority and limit
        alerts.sort(key=lambda x: DashboardAlertService.PRIORITY_LEVELS[x["priority"]])
        return {
            "alerts": alerts[:max_alerts],
            "total_alerts": len(alerts),
            "hidden_count": max(0, len(alerts) - max_alerts),
        }

    @staticmethod
    def get_alert_summary() -> Dict:
        """Get summary counts for navigation badge"""

        # Get expiration warning days from settings
        from ..utils.settings import get_setting

        days_ahead = get_setting("alerts.expiration_warning_days", 7)

        expiration_data = CombinedInventoryAlertService.get_expiration_alerts(
            days_ahead
        )
        stock_summary = CombinedInventoryAlertService.get_unified_stock_summary()
        stuck_batches = len(DashboardAlertService._get_stuck_batches())
        recent_faults = DashboardAlertService._get_recent_faults()
        timer_alerts = DashboardAlertService._get_timer_alerts()

        critical_count = (
            expiration_data["expired_total"]
            + stuck_batches
            + (1 if recent_faults > 0 else 0)
            + stock_summary["out_of_stock_count"]
        )
        high_count = (
            expiration_data["expiring_soon_total"]
            + stock_summary["low_stock_ingredients_count"]
            + timer_alerts["expired_count"]
            + stock_summary["low_stock_count"]
        )

        return {
            "critical_count": critical_count,
            "high_count": high_count,
            "total_count": critical_count + high_count,
        }

    @staticmethod
    def _get_stuck_batches() -> List:
        """Get batches that have been in progress for more than 24 hours"""
        from ..utils.timezone_utils import TimezoneUtils

        cutoff_time = TimezoneUtils.utc_now() - timedelta(hours=24)

        # Get all in-progress batches and filter with safe datetime comparison
        query = Batch.query.filter(Batch.status == "in_progress")

        if (
            current_user
            and current_user.is_authenticated
            and current_user.organization_id
        ):
            query = query.filter(Batch.organization_id == current_user.organization_id)

        all_batches = query.all()
        stuck_batches = []

        for batch in all_batches:
            if batch.started_at and TimezoneUtils.safe_datetime_compare(
                cutoff_time, batch.started_at, assume_utc=True
            ):
                stuck_batches.append(batch)

        return stuck_batches

    @staticmethod
    def _get_recent_faults() -> int:
        """Get count of recent critical faults"""
        fault_file = "faults.json"
        if not os.path.exists(fault_file):
            return 0

        faults = read_json_file(fault_file, default=[]) or []
        if not faults:
            return 0

        from ..utils.timezone_utils import TimezoneUtils

        cutoff_time = TimezoneUtils.utc_now() - timedelta(hours=24)
        recent_critical = 0

        for fault in faults:
            raw_timestamp = fault.get("timestamp")
            if not raw_timestamp:
                continue

            try:
                fault_time = datetime.fromisoformat(
                    raw_timestamp.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            # Ensure both datetimes are timezone-aware for safe comparison
            fault_time = TimezoneUtils.ensure_timezone_aware(fault_time)
            cutoff_time_aware = TimezoneUtils.ensure_timezone_aware(cutoff_time)

            if TimezoneUtils.safe_datetime_compare(
                fault_time, cutoff_time_aware, assume_utc=True
            ) and fault.get("severity", "").lower() in ["critical", "error"]:
                recent_critical += 1

        return recent_critical

    @staticmethod
    def _get_timer_alerts() -> Dict:
        """Get timer-related alerts and auto-complete expired timers"""
        try:
            # Auto-complete expired timers first
            from ..services.timer_service import TimerService

            TimerService.complete_expired_timers()

            # Use BatchTimer model which exists in your system
            from ..models import BatchTimer
            from ..utils.timezone_utils import TimezoneUtils

            # Get active timers with simple organization scoping
            query = BatchTimer.query.filter_by(status="active")

            if (
                current_user
                and current_user.is_authenticated
                and current_user.organization_id
            ):
                query = query.filter(
                    BatchTimer.organization_id == current_user.organization_id
                )

            active_timers = query.all()
            expired_timers = []

            current_time = TimezoneUtils.utc_now()

            for timer in active_timers:
                if timer.start_time and timer.duration_seconds:
                    end_time = timer.start_time + timedelta(
                        seconds=timer.duration_seconds
                    )
                    if TimezoneUtils.safe_datetime_compare(
                        current_time, end_time, assume_utc=True
                    ):
                        expired_timers.append(timer)

            return {
                "expired_count": len(expired_timers),
                "expired_timers": expired_timers,
                "active_count": len(active_timers),
            }
        except (ImportError, AttributeError) as e:
            # Fallback if BatchTimer doesn't exist or import fails
            print(f"Timer alerts error: {e}")
            return {"expired_count": 0, "expired_timers": [], "active_count": 0}

    @staticmethod
    def _get_product_inventory_issues() -> int:
        """Get count of products with inventory issues"""
        try:
            from ..models.product import ProductSKU

            # SKUs with zero or negative inventory - simple organization scoping
            query = ProductSKU.query.filter(ProductSKU.current_quantity <= 0)

            if (
                current_user
                and current_user.is_authenticated
                and current_user.organization_id
            ):
                query = query.filter(
                    ProductSKU.organization_id == current_user.organization_id
                )

            issues = query.count()
            return issues
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/dashboard_alerts.py:431", exc_info=True)
            return 0

    @staticmethod
    def _get_incomplete_batches() -> int:
        """Get count of batches missing required data"""
        try:
            # Batches that are finished but missing containers or labels
            query = Batch.query.filter(
                Batch.status == "finished", Batch.final_yield.is_(None)
            )

            # Simple organization scoping
            if (
                current_user
                and current_user.is_authenticated
                and current_user.organization_id
            ):
                query = query.filter(
                    Batch.organization_id == current_user.organization_id
                )

            incomplete = query.count()
            return incomplete
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/dashboard_alerts.py:455", exc_info=True)
            return 0
