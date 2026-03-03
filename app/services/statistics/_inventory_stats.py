"""
Inventory Statistics Service

Handles inventory efficiency tracking, spoilage monitoring,
freshness analysis, and cost impact calculations.
"""

import logging
from typing import Any, Dict

from ...extensions import db
from ...models import InventoryItem, UnifiedInventoryHistory
from ...models.statistics import InventoryEfficiencyStats
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


class InventoryStatisticsService:
    """Service for tracking inventory-level statistics"""

    @staticmethod
    def log_inventory_change(
        inventory_item_id: int, change_type: str, quantity_change: float, **context
    ):
        """Deprecated: Inventory changes are already logged in UnifiedInventoryHistory via canonical adjustment flows.
        This method now only updates efficiency projections.
        """
        try:
            # Update efficiency stats projection only
            InventoryStatisticsService._update_efficiency_stats(
                inventory_item_id,
                change_type,
                quantity_change,
                context.get("cost_impact", 0.0),
            )

            db.session.commit()
            logger.info(
                f"Updated efficiency stats for item {inventory_item_id} ({change_type} {quantity_change})"
            )

        except Exception as e:
            logger.error(f"Error updating inventory stats: {e}")
            db.session.rollback()

    @staticmethod
    def _update_efficiency_stats(
        inventory_item_id: int,
        change_type: str,
        quantity_change: float,
        cost_impact: float,
    ):
        """Update efficiency statistics based on inventory change"""
        try:
            inventory_item = db.session.get(InventoryItem, inventory_item_id)
            if not inventory_item:
                return

            # Get or create efficiency stats
            efficiency_stats = InventoryEfficiencyStats.query.filter_by(
                inventory_item_id=inventory_item_id
            ).first()

            if not efficiency_stats:
                efficiency_stats = InventoryEfficiencyStats(
                    inventory_item_id=inventory_item_id,
                    organization_id=inventory_item.organization_id,
                )
                db.session.add(efficiency_stats)

            # Update stats based on change type
            if change_type in ["purchase", "restock", "adjustment_add"]:
                efficiency_stats.total_purchased_quantity += abs(quantity_change)
                efficiency_stats.total_purchase_cost += abs(cost_impact)

            elif change_type in ["use", "production", "batch_consumption"]:
                efficiency_stats.total_used_quantity += abs(quantity_change)

            elif change_type in ["spoilage", "expired"]:
                efficiency_stats.total_spoiled_quantity += abs(quantity_change)
                efficiency_stats.total_spoilage_cost += abs(cost_impact)

            elif change_type in ["waste", "damage", "theft", "loss"]:
                efficiency_stats.total_wasted_quantity += abs(quantity_change)
                efficiency_stats.total_waste_cost += abs(cost_impact)

            # Recalculate efficiency metrics
            efficiency_stats.recalculate_efficiency()

        except Exception as e:
            logger.error(f"Error updating efficiency stats: {e}")

    @staticmethod
    def calculate_freshness_impact(inventory_item_id: int) -> Dict[str, Any]:
        """Calculate freshness impact on inventory efficiency"""
        try:
            # Get all events for this item from UnifiedInventoryHistory
            change_logs = (
                UnifiedInventoryHistory.query.filter_by(
                    inventory_item_id=inventory_item_id
                )
                .order_by(UnifiedInventoryHistory.timestamp.desc())
                .all()
            )

            if not change_logs:
                return {}

            # Analyze freshness patterns
            spoilage_events = [
                log
                for log in change_logs
                if log.change_type in ["spoil", "expired", "damaged", "trash"]
            ]
            usage_events = [
                log
                for log in change_logs
                if log.change_type in ["use", "production", "batch"]
            ]

            freshness_analysis = {
                "total_spoilage_events": len(spoilage_events),
                "total_usage_events": len(usage_events),
                "avg_days_to_spoilage": 0,
                "avg_days_to_usage": 0,
                "freshness_efficiency_score": 100.0,
            }

            # Helper to compute age in days from lot received_date
            def _age_days_for_event(e):
                try:
                    if (
                        getattr(e, "affected_lot", None)
                        and getattr(e.affected_lot, "received_date", None)
                        and getattr(e, "timestamp", None)
                    ):
                        delta = e.timestamp - e.affected_lot.received_date
                        return max(0, delta.days)
                except Exception:
                    logger.warning("Suppressed exception fallback at app/services/statistics/_inventory_stats.py:140", exc_info=True)
                    return None
                return None

            # Calculate average days to spoilage
            if spoilage_events:
                spoilage_days = [
                    d
                    for d in (_age_days_for_event(ev) for ev in spoilage_events)
                    if d is not None
                ]
                if spoilage_days:
                    freshness_analysis["avg_days_to_spoilage"] = sum(
                        spoilage_days
                    ) / len(spoilage_days)

            # Calculate average days to usage
            if usage_events:
                usage_days = [
                    d
                    for d in (_age_days_for_event(ev) for ev in usage_events)
                    if d is not None
                ]
                if usage_days:
                    freshness_analysis["avg_days_to_usage"] = sum(usage_days) / len(
                        usage_days
                    )

            # Calculate efficiency score (higher is better)
            total_events = len(spoilage_events) + len(usage_events)
            if total_events > 0:
                freshness_analysis["freshness_efficiency_score"] = (
                    len(usage_events) / total_events
                ) * 100

            return freshness_analysis

        except Exception as e:
            logger.error(f"Error calculating freshness impact: {e}")
            return {}

    @staticmethod
    def get_spoilage_report(organization_id: int, days: int = 30) -> Dict[str, Any]:
        """Get spoilage report for organization"""
        try:
            from datetime import timedelta

            since_date = TimezoneUtils.utc_now() - timedelta(days=days)

            spoilage_logs = UnifiedInventoryHistory.query.filter(
                UnifiedInventoryHistory.organization_id == organization_id,
                UnifiedInventoryHistory.change_type.in_(
                    ["spoil", "expired", "damaged", "trash"]
                ),
                UnifiedInventoryHistory.timestamp >= since_date,
            ).all()

            total_spoilage_cost = sum(log.cost_impact for log in spoilage_logs)
            total_spoiled_quantity = sum(
                abs(log.quantity_change) for log in spoilage_logs
            )

            # Group by inventory item
            spoilage_by_item = {}
            for log in spoilage_logs:
                item_name = (
                    log.inventory_item.name
                    if getattr(log, "inventory_item", None)
                    else "Unknown"
                )
                if item_name not in spoilage_by_item:
                    spoilage_by_item[item_name] = {
                        "quantity": 0,
                        "cost": 0,
                        "events": 0,
                    }
                spoilage_by_item[item_name]["quantity"] += abs(log.quantity_change)
                spoilage_by_item[item_name]["cost"] += log.cost_impact
                spoilage_by_item[item_name]["events"] += 1

            return {
                "period_days": days,
                "total_spoilage_cost": total_spoilage_cost,
                "total_spoiled_quantity": total_spoiled_quantity,
                "spoilage_events_count": len(spoilage_logs),
                "spoilage_by_item": spoilage_by_item,
                "avg_spoilage_per_event": (
                    total_spoilage_cost / len(spoilage_logs) if spoilage_logs else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error generating spoilage report: {e}")
            return {}
