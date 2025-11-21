"""
Production Cost Calculation

Handles all cost-related calculations for production planning including:
- Ingredient costs
- Container costs  
- Total production costs
- Cost per unit analysis
"""

import logging
from decimal import Decimal
from typing import List, Optional

from ...extensions import db
from ...models import Recipe
from ..unit_conversion.unit_conversion import ConversionEngine
from .types import IngredientRequirement, ContainerStrategy, CostBreakdown

logger = logging.getLogger(__name__)


def calculate_comprehensive_costs(
    ingredients: List[IngredientRequirement],
    container_strategy: Optional[ContainerStrategy],
    recipe: Recipe,
    scale: float
) -> CostBreakdown:
    """Calculate comprehensive cost breakdown for production"""

    try:
        # Calculate ingredient costs
        ingredient_costs = []
        total_ingredient_cost = Decimal('0.00')

        for ingredient in ingredients:
            cost_data = {
                'ingredient_name': ingredient.ingredient_name,
                'quantity': ingredient.scaled_quantity,
                'unit': ingredient.unit,
                'cost_per_unit': ingredient.cost_per_unit,
                'total_cost': ingredient.total_cost
            }
            ingredient_costs.append(cost_data)
            total_ingredient_cost += Decimal(str(ingredient.total_cost))

        # Calculate container costs
        container_costs = []
        total_container_cost = Decimal('0.00')

        if container_strategy:
            for container in container_strategy.selected_containers:
                container_total_cost = container.cost_each * container.containers_needed
                cost_data = {
                    'container_name': container.container_name,
                    'quantity_needed': container.containers_needed,
                    'cost_each': container.cost_each,
                    'total_cost': container_total_cost
                }
                container_costs.append(cost_data)
                total_container_cost += Decimal(str(container_total_cost))

        # Calculate totals
        total_production_cost = total_ingredient_cost + total_container_cost

        # Calculate cost per unit
        yield_amount = (recipe.predicted_yield or 0) * scale
        cost_per_unit = float(total_production_cost) / yield_amount if yield_amount > 0 else 0

        return CostBreakdown(
            ingredient_costs=ingredient_costs,
            container_costs=container_costs,
            total_ingredient_cost=float(total_ingredient_cost),
            total_container_cost=float(total_container_cost),
            total_production_cost=float(total_production_cost),
            cost_per_unit=cost_per_unit,
            yield_amount=yield_amount,
            yield_unit=recipe.predicted_yield_unit or 'count'
        )

    except Exception as e:
        logger.error(f"Error calculating comprehensive costs: {e}")
        # Return zero costs in case of error
        return CostBreakdown(
            ingredient_costs=[],
            container_costs=[],
            total_ingredient_cost=0.0,
            total_container_cost=0.0,
            total_production_cost=0.0,
            cost_per_unit=0.0,
            yield_amount=(recipe.predicted_yield or 0) * scale,
            yield_unit=recipe.predicted_yield_unit or 'count'
        )


def calculate_production_costs(recipe_id: int, scale: float = 1.0) -> dict:
    """Legacy compatibility function for cost calculation"""
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        # Simple cost calculation for backwards compatibility
        total_cost = Decimal('0.00')
        ingredient_costs = []

        for recipe_ingredient in recipe.recipe_ingredients:
            cost_per_unit = getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0
            scaled_quantity = recipe_ingredient.quantity * scale
            ingredient_cost = Decimal(str(cost_per_unit)) * Decimal(str(scaled_quantity))

            total_cost += ingredient_cost

            ingredient_costs.append({
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'quantity': scaled_quantity,
                'unit': recipe_ingredient.unit,
                'cost_per_unit': float(cost_per_unit),
                'total_cost': float(ingredient_cost)
            })

        # Calculate cost per unit if yield is known
        cost_per_unit = 0
        yield_amount = 0
        if recipe.predicted_yield and recipe.predicted_yield > 0:
            yield_amount = recipe.predicted_yield * scale
            cost_per_unit = float(total_cost) / yield_amount

        return {
            'total_cost': float(total_cost),
            'cost_per_unit': cost_per_unit,
            'yield_amount': yield_amount,
            'yield_unit': recipe.predicted_yield_unit or 'count',
            'ingredient_costs': ingredient_costs
        }

    except Exception as e:
        logger.error(f"Error calculating production costs: {e}")
        return {'error': str(e)}


def analyze_cost_breakdown(cost_breakdown: CostBreakdown) -> dict:
    """Analyze cost breakdown and provide insights"""

    analysis = {
        'cost_efficiency': 'good',  # good, fair, poor
        'ingredient_percentage': 0,
        'container_percentage': 0,
        'recommendations': []
    }

    if cost_breakdown.total_production_cost > 0:
        analysis['ingredient_percentage'] = (cost_breakdown.total_ingredient_cost / cost_breakdown.total_production_cost) * 100
        analysis['container_percentage'] = (cost_breakdown.total_container_cost / cost_breakdown.total_production_cost) * 100

        # Cost efficiency analysis
        if cost_breakdown.cost_per_unit > 10:  # Example threshold
            analysis['cost_efficiency'] = 'poor'
            analysis['recommendations'].append('Consider bulk purchasing or recipe optimization')
        elif cost_breakdown.cost_per_unit > 5:
            analysis['cost_efficiency'] = 'fair'
            analysis['recommendations'].append('Look for opportunities to reduce ingredient costs')

        # Container cost analysis
        if analysis['container_percentage'] > 30:
            analysis['recommendations'].append('Container costs are high - consider reusable containers or bulk sizes')

    return analysis