"""
Production Planning Operations

Handles planning production batches from recipes, checking stock availability,
and calculating requirements.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal

from ...models import Recipe, RecipeIngredient, InventoryItem
from ...services.stock_check import UniversalStockCheckService

logger = logging.getLogger(__name__)


def plan_production(recipe_id: int, scale: float = 1.0,
                   container_id: int = None) -> Dict[str, Any]:
    """
    Plan production for a recipe with stock checking.

    Args:
        recipe_id: Recipe to plan
        scale: Scaling factor for recipe
        container_id: Optional container for batch

    Returns:
        Dict with planning results including stock status and requirements
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Calculate requirements
        requirements = calculate_recipe_requirements(recipe_id, scale)
        if not requirements['success']:
            return requirements

        # Check ingredient availability
        availability = check_ingredient_availability(recipe_id, scale)

        # Calculate costs
        cost_info = calculate_production_cost(recipe_id, scale)

        return {
            'success': True,
            'recipe': recipe,
            'scale': scale,
            'requirements': requirements['ingredients'],
            'availability': availability,
            'cost_info': cost_info,
            'container_id': container_id,
            'can_produce': availability['all_available'],
            'missing_ingredients': availability.get('missing', []),
            'yield_amount': recipe.yield_amount * scale,
            'yield_unit': recipe.yield_unit
        }

    except Exception as e:
        logger.error(f"Error planning production for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_recipe_requirements(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate scaled ingredient requirements for a recipe.

    Args:
        recipe_id: Recipe to calculate for
        scale: Scaling factor

    Returns:
        Dict with success status and ingredient requirements
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        ingredients = []
        for recipe_ingredient in recipe.ingredients:
            scaled_quantity = recipe_ingredient.quantity * scale

            ingredients.append({
                'id': recipe_ingredient.inventory_item_id,
                'name': recipe_ingredient.inventory_item.name,
                'required_quantity': scaled_quantity,
                'required_unit': recipe_ingredient.unit,
                'original_quantity': recipe_ingredient.quantity,
                'scale_factor': scale,
                'item_type': recipe_ingredient.inventory_item.type
            })

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale': scale,
            'ingredients': ingredients,
            'total_ingredients': len(ingredients)
        }

    except Exception as e:
        logger.error(f"Error calculating requirements for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def check_ingredient_availability(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check if all ingredients are available for production using new stock check system.

    Args:
        recipe_id: Recipe to check
        scale: Scaling factor

    Returns:
        Dict with availability status and details
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Use new universal stock check service
        stock_service = UniversalStockCheckService()
        result = stock_service.check_recipe_stock(recipe, scale)

        # Transform results to match expected format
        availability_results = []
        missing_ingredients = []

        for item in result['stock_check']:
            ingredient_result = {
                'ingredient_id': item['item_id'],
                'ingredient_name': item['name'],
                'required_quantity': item['needed'],
                'required_unit': item['needed_unit'],
                'available_quantity': item['available'],
                'is_available': item['status'] in ['OK', 'LOW'],
                'shortage': max(0, item['needed'] - item['available'])
            }

            availability_results.append(ingredient_result)

            if not ingredient_result['is_available']:
                missing_ingredients.append(ingredient_result)

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale': scale,
            'all_available': result['all_ok'],
            'ingredients': availability_results,
            'missing': missing_ingredients,
            'total_missing': len(missing_ingredients)
        }

    except Exception as e:
        logger.error(f"Error checking availability for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_production_cost(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate the cost to produce a scaled recipe.

    Args:
        recipe_id: Recipe to calculate cost for
        scale: Scaling factor

    Returns:
        Dict with cost breakdown
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        total_cost = Decimal('0.00')
        ingredient_costs = []

        for recipe_ingredient in recipe.ingredients:
            required_quantity = recipe_ingredient.quantity * scale
            item = recipe_ingredient.inventory_item

            # Calculate cost for this ingredient
            if item.cost_per_unit:
                ingredient_cost = Decimal(str(item.cost_per_unit)) * Decimal(str(required_quantity))
                total_cost += ingredient_cost

                ingredient_costs.append({
                    'ingredient_id': item.id,
                    'ingredient_name': item.name,
                    'quantity': required_quantity,
                    'unit': recipe_ingredient.unit,
                    'unit_cost': float(item.cost_per_unit),
                    'total_cost': float(ingredient_cost)
                })
            else:
                ingredient_costs.append({
                    'ingredient_id': item.id,
                    'ingredient_name': item.name,
                    'quantity': required_quantity,
                    'unit': recipe_ingredient.unit,
                    'unit_cost': 0.0,
                    'total_cost': 0.0
                })

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale': scale,
            'total_cost': float(total_cost),
            'ingredient_costs': ingredient_costs,
            'cost_per_unit': float(total_cost / Decimal(str(recipe.yield_amount * scale))) if recipe.yield_amount > 0 else 0.0
        }

    except Exception as e:
        logger.error(f"Error calculating cost for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def get_missing_ingredients(recipe_id: int, scale: float = 1.0) -> List[Dict[str, Any]]:
    """
    Get list of missing ingredients for production.

    Args:
        recipe_id: Recipe to check
        scale: Scaling factor

    Returns:
        List of missing ingredient details
    """
    try:
        availability = check_ingredient_availability(recipe_id, scale)
        if availability['success']:
            return availability.get('missing', [])
        return []
    except Exception as e:
        logger.error(f"Error getting missing ingredients: {e}")
        return []