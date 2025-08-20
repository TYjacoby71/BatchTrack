
"""
Production Planning Operations

Handles planning production batches from recipes, checking stock availability,
and calculating requirements using the UniversalStockCheckService.
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
    Plan production for a recipe with comprehensive stock checking.

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

        # Use UniversalStockCheckService for comprehensive checking
        stock_service = UniversalStockCheckService()
        stock_results = stock_service.check_recipe_stock(recipe, scale)

        # Calculate requirements and costs
        requirements = calculate_recipe_requirements(recipe_id, scale)
        cost_info = calculate_production_cost(recipe_id, scale)

        # Format availability data for frontend
        availability = _format_availability_results(stock_results['stock_check'])

        return {
            'success': True,
            'recipe': recipe,
            'scale': scale,
            'requirements': requirements['ingredients'] if requirements['success'] else [],
            'availability': availability,
            'cost_info': cost_info,
            'container_id': container_id,
            'can_produce': stock_results['all_ok'],
            'missing_ingredients': availability.get('missing', []),
            'yield_amount': (recipe.predicted_yield or 0) * scale,
            'yield_unit': recipe.predicted_yield_unit or 'count'
        }

    except Exception as e:
        logger.error(f"Error planning production for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_recipe_requirements(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate ingredient requirements for a recipe at given scale.
    
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
                'ingredient_id': recipe_ingredient.inventory_item_id,
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'base_quantity': recipe_ingredient.quantity,
                'scaled_quantity': scaled_quantity,
                'unit': recipe_ingredient.unit,
                'cost_per_unit': getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0
            })

        return {
            'success': True,
            'ingredients': ingredients,
            'recipe_id': recipe_id,
            'scale': scale
        }

    except Exception as e:
        logger.error(f"Error calculating requirements for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def check_ingredient_availability(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check availability of all ingredients for a recipe using UniversalStockCheckService.
    
    Args:
        recipe_id: Recipe to check
        scale: Scaling factor
        
    Returns:
        Dict with availability results
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Use the UniversalStockCheckService
        stock_service = UniversalStockCheckService()
        results = stock_service.check_recipe_stock(recipe, scale)

        return _format_availability_results(results['stock_check'], results['all_ok'])

    except Exception as e:
        logger.error(f"Error checking ingredient availability for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_production_cost(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Calculate the cost of producing a recipe at given scale.
    
    Args:
        recipe_id: Recipe to calculate cost for
        scale: Scaling factor
        
    Returns:
        Dict with cost information
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'error': 'Recipe not found'}

        total_cost = Decimal('0.00')
        ingredient_costs = []

        for recipe_ingredient in recipe.ingredients:
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
        if recipe.predicted_yield and recipe.predicted_yield > 0:
            yield_amount = recipe.predicted_yield * scale
            cost_per_unit = float(total_cost) / yield_amount

        return {
            'total_cost': float(total_cost),
            'cost_per_unit': cost_per_unit,
            'yield_amount': (recipe.predicted_yield or 0) * scale,
            'yield_unit': recipe.predicted_yield_unit or 'count',
            'ingredient_costs': ingredient_costs
        }

    except Exception as e:
        logger.error(f"Error calculating production cost for recipe {recipe_id}: {e}")
        return {'error': str(e)}


def _format_availability_results(stock_check_results: List[Dict], all_available: bool = None) -> Dict[str, Any]:
    """
    Format stock check results for the frontend.
    
    Args:
        stock_check_results: Results from UniversalStockCheckService
        all_available: Overall availability status
        
    Returns:
        Formatted availability data
    """
    ingredients = []
    missing = []
    
    for result in stock_check_results:
        # Skip non-ingredient items (containers, etc.)
        if result.get('category') != 'ingredient':
            continue
            
        ingredient_data = {
            'ingredient_id': result['item_id'],
            'ingredient_name': result['item_name'],
            'required_quantity': result['needed_quantity'],
            'required_unit': result['needed_unit'],
            'available_quantity': result['available_quantity'],
            'available_unit': result['available_unit'],
            'is_available': result['status'] in ['OK', 'LOW'],
            'status': result['status'],
            'shortage': max(0, result['needed_quantity'] - result['available_quantity'])
        }
        
        ingredients.append(ingredient_data)
        
        # Track missing ingredients
        if not ingredient_data['is_available']:
            missing.append({
                'name': ingredient_data['ingredient_name'],
                'needed': ingredient_data['required_quantity'],
                'available': ingredient_data['available_quantity'],
                'unit': ingredient_data['required_unit'],
                'shortage': ingredient_data['shortage']
            })

    return {
        'ingredients': ingredients,
        'missing': missing,
        'all_available': all_available if all_available is not None else len(missing) == 0,
        'total_ingredients': len(ingredients),
        'available_ingredients': len(ingredients) - len(missing)
    }
