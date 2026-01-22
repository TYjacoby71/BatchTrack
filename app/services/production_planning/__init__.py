"""
Production Planning Service Package

Handles the complex orchestration of production planning including:
- Recipe scaling and requirements calculation
- Stock validation via USCS
- Container selection and fill logic
- Cost analysis
- Batch preparation

This service sits between Recipe Service and Batch Service, orchestrating
the flow from recipe → stock check → container selection → batch creation.
"""

from ._core import (
    plan_production_comprehensive
)
from ._container_management import (
    analyze_container_options
)
from ._cost_calculation import (
    calculate_production_costs,
    analyze_cost_breakdown
)
from ._batch_preparation import (
    prepare_batch_data,
    generate_batch_plan
)
from .queue_service import BatchQueueService
from .types import (
    ProductionPlan,
    ProductionRequest,
    ContainerStrategy,
    CostBreakdown
)

# Main public interface
__all__ = [
    'plan_production_comprehensive',
    'analyze_container_options',
    'calculate_production_costs',
    'analyze_cost_breakdown',
    'prepare_batch_data',
    'generate_batch_plan',
    'ProductionPlan',
    'ProductionRequest', 
    'ContainerStrategy',
    'CostBreakdown',
    'BatchQueueService',
]

# Legacy compatibility - keep existing interface working
def plan_production(recipe_id: int, scale: float = 1.0, container_id: int = None, check_containers: bool = False):
    """Legacy compatibility wrapper"""
    from ._core import plan_production_comprehensive
    return plan_production_comprehensive(
        recipe_id=recipe_id,
        scale=scale,
        preferred_container_id=container_id,
        include_container_analysis=check_containers
    )