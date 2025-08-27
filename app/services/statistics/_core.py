
"""
Core Statistics Service

Main orchestration for all statistical tracking and updates.
"""

import logging
from typing import Dict, Any, Optional
from flask_login import current_user

from ...extensions import db
from ...models.statistics import (
    UserStats, OrganizationStats, BatchStats, RecipeStats, 
    InventoryEfficiencyStats, OrganizationLeaderboardStats,
    InventoryChangeLog
)

logger = logging.getLogger(__name__)


class StatisticsService:
    """Main statistics service coordinator"""
    
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
    
    @staticmethod
    def get_organization_dashboard_stats(organization_id: int) -> Dict[str, Any]:
        """Get comprehensive stats for organization dashboard"""
        try:
            from ._reporting import ReportingService
            return ReportingService.get_organization_dashboard(organization_id)
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}
    
    @staticmethod
    def _update_recipe_stats(recipe_id: int):
        """Update recipe statistics after batch completion"""
        from ._recipe_stats import RecipeStatisticsService
        RecipeStatisticsService.recalculate_recipe_stats(recipe_id)
    
    @staticmethod
    def _update_organization_stats(organization_id: int):
        """Update organization-level statistics"""
        org_stats = OrganizationStats.get_or_create(organization_id)
        org_stats.refresh_from_database()
        
        # Update leaderboard stats
        leaderboard_stats = OrganizationLeaderboardStats.get_or_create(organization_id)
        # Recalculation logic would go here
        
        db.session.commit()
