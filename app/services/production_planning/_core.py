"""
Production Planning Core

Main orchestration logic that coordinates:
- Recipe requirements via USCS
- Container analysis  
- Cost calculation
- Data prep for batch handoff
"""

import logging
from typing import Dict, Any, Optional
from flask_login import current_user

from ...models import Recipe
from ..stock_check import UniversalStockCheckService
from .types import ProductionRequest, ProductionPlan, IngredientRequirement, CostBreakdown
from ._container_management import analyze_container_options
from ._cost_calculation import calculate_comprehensive_costs

logger = logging.getLogger(__name__)


def plan_production_comprehensive(
    recipe_id: int,
    scale: float = 1.0,
    preferred_container_id: Optional[int] = None,
    include_container_analysis: bool = True,
    max_cost_per_unit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Main production planning orchestration.

    Coordinates: Recipe → USCS stock check → Container analysis → Batch prep
    """
    try:
        # Create production request
        request = ProductionRequest(
            recipe_id=recipe_id,
            scale=scale,
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )

        # Execute planning
        plan = execute_production_planning(request, include_container_analysis)

        # Return as dictionary for API compatibility
        return plan.to_dict()

    except Exception as e:
        logger.error(f"Error in production planning: {e}")
        return {
            'success': False,
            'feasible': False,
            'error': f'Production planning failed: {str(e)}',
            'stock_results': [],
            'issues': [f'Production planning failed: {str(e)}']
        }


def execute_production_planning(request: ProductionRequest, include_containers: bool = True) -> ProductionPlan:
    """Execute the production planning workflow"""
    from ._stock_validation import validate_ingredients_with_uscs

    # 1. Load recipe
    recipe = Recipe.query.get(request.recipe_id)
    if not recipe:
        raise ValueError(f"Recipe {request.recipe_id} not found")

    logger.info(f"PRODUCTION_PLANNING: Starting analysis for recipe {recipe.name} at scale {request.scale}")

    # 2. Validate ingredients using stock validation service
    ingredient_requirements = validate_ingredients_with_uscs(
        recipe, request.scale, request.organization_id or (current_user.organization_id if current_user.is_authenticated else None)
    )

    if not ingredient_requirements:
        return ProductionPlan(
            request=request,
            feasible=False,
            ingredient_requirements=[],
            projected_yield={'amount': 0, 'unit': 'count'},
            issues=['Stock validation failed - no ingredients found']
        )

    # 3. Analyze containers if requested
    container_strategy = None
    container_options = []
    if include_containers:
        raw_strategy, raw_container_options = analyze_container_options(
            recipe, request.scale, None, request.organization_id, api_format=False
        )
        
        if raw_strategy:
            # Convert to typed objects
            container_strategy = ContainerStrategy(
                selected_containers=[
                    ContainerOption(
                        container_id=opt['container_id'],
                        container_name=opt['container_name'],
                        capacity=opt['capacity'],
                        available_quantity=opt['available_quantity'],
                        containers_needed=opt['containers_needed'],
                        cost_each=opt.get('cost_each', 0.0)
                    ) for opt in raw_strategy.get('container_selection', [])
                ],
                total_capacity=raw_strategy.get('total_capacity', 0),
                containment_percentage=raw_strategy.get('containment_percentage', 0),
                warnings=raw_strategy.get('warnings', [])
            )
        
        # All available container options
        for opt in raw_container_options:
            container_options.append(ContainerOption(
                container_id=opt['container_id'],
                container_name=opt['container_name'],
                capacity=opt['capacity'],
                available_quantity=opt['available_quantity'],
                containers_needed=opt['containers_needed'],
                cost_each=opt.get('cost_each', 0.0)
            ))

    # 4. Calculate costs
    cost_breakdown = calculate_comprehensive_costs(
        ingredient_requirements,
        container_strategy,
        recipe,
        request.scale
    )

    # 5. Determine feasibility
    feasible = all(req.status in ['available', 'OK'] for req in ingredient_requirements)
    issues = []
    if not feasible:
        issues.append("Insufficient ingredients available")
    if include_containers and not container_strategy:
        issues.append("No suitable containers found")
        feasible = False

    # 6. Create production plan
    plan = ProductionPlan(
        request=request,
        feasible=feasible,
        ingredient_requirements=ingredient_requirements,
        projected_yield={
            'amount': (recipe.predicted_yield or 0) * request.scale,
            'unit': recipe.predicted_yield_unit or 'count'
        },
        container_strategy=container_strategy,
        container_options=container_options,
        cost_breakdown=cost_breakdown,
        issues=issues
    )

    logger.info(f"PRODUCTION_PLANNING: Analysis complete - Feasible: {plan.feasible}")
    return plan