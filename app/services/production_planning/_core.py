"""
Production Planning Core

Main orchestration logic that coordinates all aspects of production planning:
- Recipe requirements calculation
- Stock validation via USCS
- Container strategy selection
- Cost analysis
- Issue identification and recommendations
"""

import logging
from typing import Dict, Any, Optional, List
from flask_login import current_user

from ...models import Recipe
from ..stock_check import UniversalStockCheckService
from .types import (
    ProductionRequest, ProductionPlan, ProductionStatus,
    IngredientRequirement, CostBreakdown
)
from ._stock_validation import validate_ingredients_with_uscs
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
    Comprehensive production planning with full analysis.

    This is the main entry point that orchestrates all production planning logic.
    """
    try:
        # Create production request
        request = ProductionRequest(
            recipe_id=recipe_id,
            scale=scale,
            preferred_container_id=preferred_container_id,
            include_container_analysis=include_container_analysis,
            max_cost_per_unit=max_cost_per_unit,
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )

        # Execute planning
        plan = execute_production_planning(request)

        # Return as dictionary for API compatibility
        return plan.to_dict()

    except Exception as e:
        logger.error(f"Error in comprehensive production planning: {e}")
        return {
            'success': False,
            'status': 'error',
            'feasible': False,
            'error': f'Production planning failed: {str(e)}',
            'message': f'Production planning failed: {str(e)}'
        }


def execute_production_planning(request: ProductionRequest) -> ProductionPlan:
    """Execute the complete production planning workflow"""

    # 1. Load and validate recipe
    recipe = Recipe.query.get(request.recipe_id)
    if not recipe:
        raise ValueError(f"Recipe {request.recipe_id} not found")

    logger.info(f"PRODUCTION_PLANNING: Starting analysis for recipe {recipe.name} at scale {request.scale}")

    # 2. Calculate ingredient requirements and validate availability
    ingredient_requirements = validate_ingredients_with_uscs(recipe, request.scale, request.organization_id)

    # 3. Analyze container options if requested
    container_strategy = None
    container_options = []
    if request.include_container_analysis:
        container_strategy, container_options = analyze_container_options(
            recipe, request.scale, request.preferred_container_id, request.organization_id
        )

    # 4. Calculate comprehensive costs
    cost_breakdown = calculate_comprehensive_costs(
        ingredient_requirements,
        container_strategy,
        recipe,
        request.scale
    )

    # 5. Determine overall feasibility status
    status, issues, recommendations = analyze_production_feasibility(
        ingredient_requirements, container_strategy, cost_breakdown, request
    )

    # 6. Create final production plan
    plan = ProductionPlan(
        request=request,
        status=status,
        feasible=status == ProductionStatus.FEASIBLE,
        ingredient_requirements=ingredient_requirements,
        projected_yield={
            'amount': (recipe.predicted_yield or 0) * request.scale,
            'unit': recipe.predicted_yield_unit or 'count'
        },
        container_strategy=container_strategy,
        container_options=container_options,
        cost_breakdown=cost_breakdown,
        issues=issues,
        recommendations=recommendations
    )

    logger.info(f"PRODUCTION_PLANNING: Analysis complete - Status: {status.value}, Feasible: {plan.feasible}")

    return plan


def analyze_production_feasibility(
    ingredients: list,
    container_strategy,
    cost_breakdown: CostBreakdown,
    request: ProductionRequest
) -> tuple:
    """Analyze overall production feasibility and generate recommendations"""

    issues = []
    recommendations = []

    # Check ingredient availability
    insufficient_ingredients = [ing for ing in ingredients if ing.status in ['insufficient', 'unavailable']]
    if insufficient_ingredients:
        issues.append(f"{len(insufficient_ingredients)} ingredients have insufficient stock")
        recommendations.append("Restock insufficient ingredients before production")
        # If we have insufficient ingredients, we can't proceed
        # We still want to return the stock check results, so we don't raise an error here.
        # The status will reflect the insufficient ingredients.
        return ProductionStatus.INSUFFICIENT_INGREDIENTS, issues, recommendations


    # Check container availability  
    if request.include_container_analysis and (not container_strategy or not container_strategy.selected_containers):
        issues.append("No suitable containers available for production")
        if not container_strategy:
            recommendations.append("Add containers to inventory or specify allowed containers for this recipe")
        return ProductionStatus.NO_CONTAINERS, issues, recommendations

    # Check cost constraints
    if request.max_cost_per_unit and cost_breakdown.cost_per_unit > request.max_cost_per_unit:
        issues.append(f"Cost per unit (${cost_breakdown.cost_per_unit:.2f}) exceeds maximum (${request.max_cost_per_unit:.2f})")
        recommendations.append("Consider scaling up production or finding lower-cost ingredients")
        return ProductionStatus.COST_PROHIBITIVE, issues, recommendations

    # Check for low stock warnings
    low_stock_ingredients = [ing for ing in ingredients if ing.status == 'low']
    if low_stock_ingredients:
        issues.append(f"{len(low_stock_ingredients)} ingredients are running low")
        recommendations.append("Consider restocking low inventory items after production")

    # Container efficiency recommendations
    if container_strategy and container_strategy.average_fill_percentage < 60:
        recommendations.append(f"Container fill efficiency is {container_strategy.average_fill_percentage:.0f}% - consider different container sizes")

    if container_strategy and container_strategy.waste_percentage > 20:
        recommendations.append(f"High container waste ({container_strategy.waste_percentage:.0f}%) - consider scaling recipe or using different containers")

    return ProductionStatus.FEASIBLE, issues, recommendations


