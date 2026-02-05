
"""Core statistics service.

Synopsis:
Coordinates statistical tracking and leaderboard refreshes.

Glossary:
- Leaderboard: Aggregated metrics for top performers.
- Recipe stats: Per-recipe performance summaries.
"""

import logging
from typing import Dict, Any, Optional
from flask_login import current_user

import sqlalchemy as sa
from ...extensions import db
from ...models.statistics import (
    UserStats, OrganizationStats, BatchStats, RecipeStats, 
    InventoryEfficiencyStats, OrganizationLeaderboardStats,
    InventoryChangeLog
)

logger = logging.getLogger(__name__)


class StatisticsService:
    """Main statistics service coordinator"""
    
    # --- Record planned efficiency ---
    # Purpose: Track planned efficiency from production planning.
    @staticmethod
    def record_planned_efficiency(recipe_id: int, planned_efficiency: float, planned_yield: Dict[str, Any], planned_costs: Dict[str, Any] = None):
        """Record planned efficiency from production planning"""
        try:
            from ._recipe_stats import RecipeStatisticsService
            
            # Update recipe planning counts
            RecipeStatisticsService.increment_batch_planned(recipe_id, current_user.organization_id)
            
            logger.info(f"Recorded planned efficiency: {planned_efficiency}% for recipe {recipe_id}")
            
        except Exception as e:
            logger.error(f"Error recording planned efficiency: {e}")
    
    # --- Record batch completion ---
    # Purpose: Store batch completion stats and refresh rollups.
    @staticmethod
    def record_batch_completion(batch_id: int, efficiency_data: Dict[str, Any]):
        """Record batch completion with efficiency data"""
        try:
            from ._batch_stats import BatchStatisticsService
            
            batch_stats = BatchStatisticsService.complete_batch(batch_id, efficiency_data)
            if batch_stats:
                # Update related recipe and organization stats
                StatisticsService._update_recipe_stats(batch_stats.recipe_id)
                StatisticsService._update_organization_stats(batch_stats.organization_id)
            
        except Exception as e:
            logger.error(f"Error recording batch completion: {e}")
    
    # --- Track inventory change ---
    # Purpose: Log inventory adjustments with context.
    @staticmethod
    def track_inventory_change(inventory_item_id: int, change_type: str, quantity_change: float, **context):
        """Track inventory changes with detailed context"""
        try:
            from ._inventory_stats import InventoryStatisticsService
            
            InventoryStatisticsService.log_inventory_change(
                inventory_item_id, change_type, quantity_change, **context
            )
            
        except Exception as e:
            logger.error(f"Error tracking inventory change: {e}")
    
    # --- Get dashboard stats ---
    # Purpose: Aggregate organization stats for dashboards.
    @staticmethod
    def get_organization_dashboard_stats(organization_id: int) -> Dict[str, Any]:
        """Get comprehensive stats for organization dashboard"""
        try:
            from ._reporting import ReportingService
            return ReportingService.get_organization_dashboard(organization_id)
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}
    
    # --- Update recipe stats ---
    # Purpose: Refresh recipe metrics after batch completion.
    @staticmethod
    def _update_recipe_stats(recipe_id: int):
        """Update recipe statistics after batch completion"""
        from ._recipe_stats import RecipeStatisticsService
        RecipeStatisticsService.recalculate_recipe_stats(recipe_id)
    
    # --- Update organization stats ---
    # Purpose: Refresh organization + leaderboard metrics.
    @staticmethod
    def _update_organization_stats(organization_id: int):
        """Update organization-level statistics"""
        from ...models import Recipe
        org_stats = OrganizationStats.get_or_create(organization_id)
        org_stats.refresh_from_database()
        
        # Update leaderboard stats
        leaderboard_stats = OrganizationLeaderboardStats.get_or_create(organization_id)
        top_tester = db.session.query(
            Recipe.created_by,
            sa.func.count(Recipe.id).label('test_count'),
        ).filter(
            Recipe.organization_id == organization_id,
            Recipe.test_sequence.is_not(None),
        ).group_by(
            Recipe.created_by
        ).order_by(
            sa.desc('test_count')
        ).first()

        if top_tester and top_tester[0]:
            leaderboard_stats.most_testing_user_id = top_tester[0]
            leaderboard_stats.most_tests_created = int(top_tester[1] or 0)
        else:
            leaderboard_stats.most_testing_user_id = None
            leaderboard_stats.most_tests_created = 0
        
        db.session.commit()
