"""
Reporting Service

Aggregates statistics data for dashboards, reports, and analytics.
"""

import logging
from datetime import timedelta
from typing import Any, Dict

from ...extensions import db
from ...models.freshness_snapshot import FreshnessSnapshot
from ...models.statistics import BatchStats, OrganizationStats, RecipeStats, UserStats
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


class ReportingService:
    """Service for generating statistical reports and dashboard data"""

    @staticmethod
    def get_organization_dashboard(organization_id: int) -> Dict[str, Any]:
        """Get comprehensive dashboard data for organization"""
        try:
            # Organization stats
            org_stats = OrganizationStats.get_or_create(organization_id)

            # Recent batch performance
            recent_batches = (
                BatchStats.query.filter(
                    BatchStats.organization_id == organization_id,
                    BatchStats.batch_status == "completed",
                )
                .order_by(BatchStats.completed_at.desc())
                .limit(10)
                .all()
            )

            avg_efficiency = 0
            if recent_batches:
                avg_efficiency = sum(
                    b.actual_fill_efficiency for b in recent_batches
                ) / len(recent_batches)

            # Top performing recipes
            top_recipes = (
                db.session.query(RecipeStats)
                .filter(RecipeStats.organization_id == organization_id)
                .order_by(RecipeStats.success_rate_percentage.desc())
                .limit(5)
                .all()
            )

            return {
                "organization_stats": {
                    "total_batches": org_stats.total_batches,
                    "completed_batches": org_stats.completed_batches,
                    "failed_batches": org_stats.failed_batches,
                    "active_users": org_stats.active_users,
                    "total_recipes": org_stats.total_recipes,
                },
                "performance_metrics": {
                    "recent_avg_efficiency": round(avg_efficiency, 2),
                    "total_batches_this_month": ReportingService._get_monthly_batch_count(
                        organization_id
                    ),
                    "success_rate": ReportingService._calculate_success_rate(
                        organization_id
                    ),
                    "avg_item_freshness_score": ReportingService._get_recent_avg_item_freshness(
                        organization_id
                    ),
                },
                "top_recipes": [
                    {
                        "recipe_id": rs.recipe_id,
                        "success_rate": rs.success_rate_percentage,
                        "total_batches": rs.total_batches_completed,
                        "avg_efficiency": rs.avg_fill_efficiency,
                    }
                    for rs in top_recipes
                ],
            }

        except Exception as e:
            logger.error(f"Error generating organization dashboard: {e}")
            return {}

    @staticmethod
    def get_user_performance_report(
        user_id: int, organization_id: int
    ) -> Dict[str, Any]:
        """Get performance report for a specific user"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)

            # User's batch performance
            user_batches = BatchStats.query.filter(
                BatchStats.user_id == user_id,
                BatchStats.organization_id == organization_id,
                BatchStats.batch_status == "completed",
            ).all()

            avg_efficiency = 0
            avg_cost_variance = 0
            if user_batches:
                avg_efficiency = sum(
                    b.actual_fill_efficiency for b in user_batches
                ) / len(user_batches)
                avg_cost_variance = sum(
                    b.cost_variance_percentage for b in user_batches
                ) / len(user_batches)

            return {
                "user_stats": {
                    "total_batches": user_stats.total_batches,
                    "completed_batches": user_stats.completed_batches,
                    "failed_batches": user_stats.failed_batches,
                    "total_recipes": user_stats.total_recipes,
                    "inventory_adjustments": user_stats.inventory_adjustments,
                },
                "performance": {
                    "avg_fill_efficiency": round(avg_efficiency, 2),
                    "avg_cost_variance": round(avg_cost_variance, 2),
                    "success_rate": (
                        (user_stats.completed_batches / user_stats.total_batches * 100)
                        if user_stats.total_batches > 0
                        else 0
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error generating user performance report: {e}")
            return {}

    @staticmethod
    def get_efficiency_trends(organization_id: int, days: int = 30) -> Dict[str, Any]:
        """Get efficiency trends over specified period"""
        try:
            since_date = TimezoneUtils.utc_now() - timedelta(days=days)

            batches = (
                BatchStats.query.filter(
                    BatchStats.organization_id == organization_id,
                    BatchStats.batch_status == "completed",
                    BatchStats.completed_at >= since_date,
                )
                .order_by(BatchStats.completed_at)
                .all()
            )

            # Group by date
            daily_efficiency = {}
            for batch in batches:
                date_key = batch.completed_at.date().isoformat()
                if date_key not in daily_efficiency:
                    daily_efficiency[date_key] = []
                daily_efficiency[date_key].append(batch.actual_fill_efficiency)

            # Calculate daily averages
            trends = []
            for date_str, efficiencies in daily_efficiency.items():
                avg_efficiency = sum(efficiencies) / len(efficiencies)
                trends.append(
                    {
                        "date": date_str,
                        "avg_efficiency": round(avg_efficiency, 2),
                        "batch_count": len(efficiencies),
                    }
                )

            return {
                "period_days": days,
                "trends": sorted(trends, key=lambda x: x["date"]),
                "overall_avg": (
                    round(
                        sum(b.actual_fill_efficiency for b in batches) / len(batches), 2
                    )
                    if batches
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error generating efficiency trends: {e}")
            return {}

    @staticmethod
    def _get_monthly_batch_count(organization_id: int) -> int:
        """Get batch count for current month"""
        try:
            now = TimezoneUtils.utc_now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            return BatchStats.query.filter(
                BatchStats.organization_id == organization_id,
                BatchStats.created_at >= month_start,
            ).count()

        except Exception as e:
            logger.error(f"Error getting monthly batch count: {e}")
            return 0

    @staticmethod
    def _get_recent_avg_item_freshness(organization_id: int) -> float:
        """Get recent average freshness efficiency score from snapshots (last 7 days)."""
        try:
            since = TimezoneUtils.utc_now() - timedelta(days=7)
            snaps = FreshnessSnapshot.query.filter(
                FreshnessSnapshot.organization_id == organization_id,
                FreshnessSnapshot.snapshot_date >= since.date(),
            ).all()
            scores = [
                s.freshness_efficiency_score
                for s in snaps
                if s.freshness_efficiency_score is not None
            ]
            if not scores:
                return 0.0
            return round(sum(scores) / len(scores), 2)
        except Exception as e:
            logger.error(f"Error computing avg item freshness: {e}")
            return 0.0

    @staticmethod
    def _calculate_success_rate(organization_id: int) -> float:
        """Calculate overall success rate for organization"""
        try:
            org_stats = OrganizationStats.get_or_create(organization_id)
            total_batches = org_stats.completed_batches + org_stats.failed_batches

            if total_batches > 0:
                return round((org_stats.completed_batches / total_batches) * 100, 2)
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating success rate: {e}")
            return 0.0
