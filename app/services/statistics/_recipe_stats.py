"""
Recipe Statistics Service

Handles recipe-level performance tracking, success rates,
and efficiency metrics across all batches.
"""

import logging
from typing import Any, Dict

from ...extensions import db
from ...models.statistics import RecipeStats
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


class RecipeStatisticsService:
    """Service for tracking recipe-level statistics"""

    @staticmethod
    def increment_batch_planned(recipe_id: int, organization_id: int):
        """Increment planned batch count for recipe"""
        try:
            recipe_stats = RecipeStats.get_or_create(recipe_id, organization_id)
            recipe_stats.total_batches_planned += 1
            recipe_stats.last_updated = TimezoneUtils.utc_now()
            db.session.commit()
            logger.info(f"Incremented planned batch count for recipe {recipe_id}")

        except Exception as e:
            logger.error(f"Error incrementing batch planned count: {e}")
            db.session.rollback()

    @staticmethod
    def increment_batch_completed(recipe_id: int, organization_id: int):
        """Increment completed batch count for recipe"""
        try:
            recipe_stats = RecipeStats.get_or_create(recipe_id, organization_id)
            recipe_stats.total_batches_completed += 1
            recipe_stats.last_batch_date = TimezoneUtils.utc_now()
            recipe_stats.last_updated = TimezoneUtils.utc_now()

            # Recalculate success rate
            total_batches = (
                recipe_stats.total_batches_completed + recipe_stats.total_batches_failed
            )
            if total_batches > 0:
                recipe_stats.success_rate_percentage = (
                    recipe_stats.total_batches_completed / total_batches
                ) * 100

            db.session.commit()
            logger.info(f"Incremented completed batch count for recipe {recipe_id}")

        except Exception as e:
            logger.error(f"Error incrementing batch completed count: {e}")
            db.session.rollback()

    @staticmethod
    def increment_batch_failed(recipe_id: int, organization_id: int):
        """Increment failed batch count for recipe"""
        try:
            recipe_stats = RecipeStats.get_or_create(recipe_id, organization_id)
            recipe_stats.total_batches_failed += 1
            recipe_stats.last_updated = TimezoneUtils.utc_now()

            # Recalculate success rate
            total_batches = (
                recipe_stats.total_batches_completed + recipe_stats.total_batches_failed
            )
            if total_batches > 0:
                recipe_stats.success_rate_percentage = (
                    recipe_stats.total_batches_completed / total_batches
                ) * 100

            db.session.commit()
            logger.info(f"Incremented failed batch count for recipe {recipe_id}")

        except Exception as e:
            logger.error(f"Error incrementing batch failed count: {e}")
            db.session.rollback()

    @staticmethod
    def recalculate_recipe_stats(recipe_id: int):
        """Recalculate all statistics for a recipe from batch data"""
        try:
            from ...models import Recipe

            recipe = db.session.get(Recipe, recipe_id)
            if not recipe:
                return

            recipe_stats = RecipeStats.get_or_create(recipe_id, recipe.organization_id)
            recipe_stats.recalculate_from_batches()
            db.session.commit()
            logger.info(f"Recalculated stats for recipe {recipe_id}")

        except Exception as e:
            logger.error(f"Error recalculating recipe stats: {e}")
            db.session.rollback()

    @staticmethod
    def get_recipe_performance_report(recipe_id: int) -> Dict[str, Any]:
        """Get comprehensive performance report for a recipe"""
        try:
            recipe_stats = RecipeStats.query.filter_by(recipe_id=recipe_id).first()
            if not recipe_stats:
                return {}

            return {
                "recipe_id": recipe_id,
                "total_batches_planned": recipe_stats.total_batches_planned,
                "total_batches_completed": recipe_stats.total_batches_completed,
                "total_batches_failed": recipe_stats.total_batches_failed,
                "success_rate_percentage": recipe_stats.success_rate_percentage,
                "avg_fill_efficiency": recipe_stats.avg_fill_efficiency,
                "avg_yield_variance": recipe_stats.avg_yield_variance,
                "avg_cost_variance": recipe_stats.avg_cost_variance,
                "avg_cost_per_batch": recipe_stats.avg_cost_per_batch,
                "avg_cost_per_unit": recipe_stats.avg_cost_per_unit,
                "total_spoilage_cost": recipe_stats.total_spoilage_cost,
                "last_batch_date": recipe_stats.last_batch_date,
                "last_updated": recipe_stats.last_updated,
            }

        except Exception as e:
            logger.error(f"Error getting recipe performance report: {e}")
            return {}
