
"""
Batch Statistics Service

Handles all batch-level statistical tracking including efficiency,
cost variance, yield analysis, and completion data.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ...extensions import db
from ...models.statistics import BatchStats
from ...models import Batch
from ...utils.timezone_utils import TimezoneUtils
from ...services.freshness_service import FreshnessService

logger = logging.getLogger(__name__)


class BatchStatisticsService:
    """Service for tracking batch-level statistics"""
    
    @staticmethod
    def create_from_production_plan(batch_id: int, production_plan: Dict[str, Any]) -> Optional[BatchStats]:
        """Create batch stats from production planning data"""
        try:
            # Extract efficiency data from production plan, with category_extension fallback
            container_strategy = production_plan.get('container_strategy', {})
            planned_efficiency = container_strategy.get('containment_percentage', 0.0)
            try:
                if not planned_efficiency:
                    cat_ext = (production_plan.get('category_extension') or {})
                    # vessel_fill_pct directly maps to fill efficiency when available
                    vfp = cat_ext.get('vessel_fill_pct')
                    if vfp is not None:
                        planned_efficiency = float(vfp)
            except Exception:
                pass
            
            # Extract yield data
            projected_yield = production_plan.get('projected_yield', {})
            
            # Extract cost data
            cost_breakdown = production_plan.get('cost_breakdown', {})
            planned_costs = {
                'ingredient_cost': cost_breakdown.get('ingredient_cost', 0.0),
                'container_cost': cost_breakdown.get('container_cost', 0.0),
                'total_cost': cost_breakdown.get('total_cost', 0.0)
            }
            
            batch_stats = BatchStats.create_from_planned_batch(
                batch_id=batch_id,
                planned_efficiency=planned_efficiency,
                planned_yield=projected_yield,
                planned_costs=planned_costs
            )
            
            db.session.commit()
            logger.info(f"Created batch stats for batch {batch_id} with {planned_efficiency}% efficiency")
            return batch_stats
            
        except Exception as e:
            logger.error(f"Error creating batch stats: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def complete_batch(batch_id: int, completion_data: Dict[str, Any]) -> Optional[BatchStats]:
        """Update batch stats with completion data"""
        try:
            batch_stats = BatchStats.query.filter_by(batch_id=batch_id).first()
            if not batch_stats:
                logger.warning(f"No batch stats found for batch {batch_id}")
                return None
            
            # Extract actual data from completion
            actual_efficiency = completion_data.get('actual_fill_efficiency', 0.0)
            actual_yield = completion_data.get('actual_yield', {})
            actual_costs = completion_data.get('actual_costs', {})
            
            # Update batch stats
            batch_stats.update_actual_data(actual_efficiency, actual_yield, actual_costs)
            batch_stats.batch_status = 'completed'
            
            # Calculate duration if available
            batch = db.session.get(Batch, batch_id)
            if batch and batch.started_at and batch.completed_at:
                duration = batch.completed_at - batch.started_at
                batch_stats.actual_duration_minutes = int(duration.total_seconds() / 60)
            
            # Compute and emit freshness metrics for analytics/warehouse
            batch = db.session.get(Batch, batch_id)
            freshness_summary = FreshnessService.compute_batch_freshness(batch) if batch else None

            # Attach lightweight metrics to stats for downstream reporting (not persisted fields)
            overall_freshness = getattr(freshness_summary, 'overall_freshness_percent', None) if freshness_summary else None

            db.session.commit()

            # Emit domain event for analytics pipeline
            try:
                from ...services.event_emitter import EventEmitter
                EventEmitter.emit(
                    event_name='batch_metrics_computed',
                    properties={
                        'batch_id': batch_id,
                        'actual_fill_efficiency': batch_stats.actual_fill_efficiency,
                        'yield_variance_percentage': batch_stats.yield_variance_percentage,
                        'cost_variance_percentage': batch_stats.cost_variance_percentage,
                        'overall_freshness_percent': overall_freshness
                    },
                    organization_id=batch.organization_id if batch else None,
                    user_id=batch.created_by if batch else None,
                    entity_type='batch',
                    entity_id=batch_id
                )
            except Exception:
                pass
            logger.info(f"Updated batch stats for completed batch {batch_id}")
            return batch_stats
            
        except Exception as e:
            logger.error(f"Error updating batch completion stats: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def mark_batch_failed(batch_id: int, failure_reason: str = None):
        """Mark batch as failed in statistics"""
        try:
            batch_stats = BatchStats.query.filter_by(batch_id=batch_id).first()
            if batch_stats:
                batch_stats.batch_status = 'failed'
                batch_stats.last_updated = TimezoneUtils.utc_now()
                db.session.commit()
                logger.info(f"Marked batch {batch_id} as failed in statistics")
                
        except Exception as e:
            logger.error(f"Error marking batch as failed: {e}")
            db.session.rollback()
    
    @staticmethod
    def get_batch_efficiency_report(batch_id: int) -> Dict[str, Any]:
        """Get comprehensive efficiency report for a batch"""
        try:
            batch_stats = BatchStats.query.filter_by(batch_id=batch_id).first()
            if not batch_stats:
                return {}
            
            return {
                'planned_efficiency': batch_stats.planned_fill_efficiency,
                'actual_efficiency': batch_stats.actual_fill_efficiency,
                'efficiency_variance': batch_stats.efficiency_variance,
                'yield_variance': batch_stats.yield_variance_percentage,
                'cost_variance': batch_stats.cost_variance_percentage,
                'total_planned_cost': batch_stats.total_planned_cost,
                'total_actual_cost': batch_stats.total_actual_cost,
                'spoilage_cost': batch_stats.ingredient_spoilage_cost + batch_stats.product_spoilage_cost,
                'batch_status': batch_stats.batch_status,
                'completed_at': batch_stats.completed_at
            }
            
        except Exception as e:
            logger.error(f"Error getting batch efficiency report: {e}")
            return {}
