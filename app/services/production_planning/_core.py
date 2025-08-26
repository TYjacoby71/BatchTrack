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

    # 1. Load recipe
    recipe = Recipe.query.get(request.recipe_id)
    if not recipe:
        raise ValueError(f"Recipe {request.recipe_id} not found")

    logger.info(f"PRODUCTION_PLANNING: Starting analysis for recipe {recipe.name} at scale {request.scale}")

    # 2. Get stock check from USCS
    uscs = UniversalStockCheckService()
    stock_results = uscs.check_recipe_stock(recipe.id, request.scale)

    if not stock_results.get('success'):
        logger.error(f"USCS stock check failed: {stock_results.get('error')}")
        return ProductionPlan(
            request=request,
            feasible=False,
            ingredient_requirements=[],
            projected_yield={'amount': 0, 'unit': 'count'},
            issues=[stock_results.get('error', 'Stock check failed')]
        )

    # 3. Convert USCS results to ingredient requirements
    ingredient_requirements = []
    for stock_item in stock_results.get('stock_check', []):
        recipe_ingredient = next(
            (ri for ri in recipe.recipe_ingredients if ri.inventory_item_id == stock_item['item_id']),
            None
        )

        if recipe_ingredient:
            requirement = IngredientRequirement(
                ingredient_id=stock_item['item_id'],
                ingredient_name=stock_item['item_name'],
                scale=request.scale,
                unit=stock_item['needed_unit'],
                total_cost=(stock_item['needed_quantity']) * (getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0),
                status=stock_item.get('status', 'unknown')
            )
            ingredient_requirements.append(requirement)

    # 4. Analyze containers if requested
    container_strategy = None
    container_options = []
    if include_containers:
        container_strategy, container_options = analyze_container_options(
            recipe, request.scale, None, request.organization_id
        )

    # 5. Calculate costs
    cost_breakdown = calculate_comprehensive_costs(
        ingredient_requirements,
        container_strategy,
        recipe,
        request.scale
    )

    # 6. Determine feasibility based on USCS results
    feasible = stock_results.get('all_ok', False)
    issues = []
    if not feasible:
        issues.append("Insufficient ingredients available")
    if include_containers and not container_strategy:
        issues.append("No suitable containers found")
        feasible = False

    # 7. Create production plan
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