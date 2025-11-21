
"""
Recipe Scaling Operations

Handles scaling recipes up or down and calculating scaled ingredient amounts.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List

from ...extensions import db
from ...models import Recipe

logger = logging.getLogger(__name__)


def scale_recipe(recipe_id: int, target_yield: float, 
                yield_unit: str = None) -> Dict[str, Any]:
    """
    Scale a recipe to achieve a target yield.
    
    Args:
        recipe_id: Recipe to scale
        target_yield: Desired yield amount
        yield_unit: Unit for target yield (must match recipe unit)
        
    Returns:
        Dict with scaling results
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Validate yield unit matches
        if yield_unit and yield_unit != recipe.yield_unit:
            return {
                'success': False, 
                'error': f'Yield unit mismatch. Recipe yields in {recipe.yield_unit}, not {yield_unit}'
            }

        # Calculate scaling factor
        scale_factor = target_yield / recipe.yield_amount
        
        # Validate scaling factor
        is_valid, error = validate_scaling_factor(scale_factor)
        if not is_valid:
            return {'success': False, 'error': error}

        # Calculate scaled ingredients
        scaled_ingredients = calculate_scaled_ingredients(recipe_id, scale_factor)
        if not scaled_ingredients['success']:
            return scaled_ingredients

        return {
            'success': True,
            'recipe_id': recipe_id,
            'original_yield': recipe.yield_amount,
            'target_yield': target_yield,
            'yield_unit': recipe.yield_unit,
            'scale_factor': scale_factor,
            'scaled_ingredients': scaled_ingredients['ingredients']
        }

    except Exception as e:
        logger.error(f"Error scaling recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def calculate_scaled_ingredients(recipe_id: int, scale_factor: float) -> Dict[str, Any]:
    """
    Calculate ingredient amounts for a scaled recipe.
    
    Args:
        recipe_id: Recipe to scale
        scale_factor: Scaling factor to apply
        
    Returns:
        Dict with scaled ingredient amounts
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        scaled_ingredients = []
        
        for recipe_ingredient in recipe.ingredients:
            original_quantity = recipe_ingredient.quantity
            scaled_quantity = original_quantity * scale_factor
            
            scaled_ingredients.append({
                'ingredient_id': recipe_ingredient.inventory_item_id,
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'original_quantity': original_quantity,
                'scaled_quantity': scaled_quantity,
                'unit': recipe_ingredient.unit,
                'scale_factor': scale_factor,
                'item_type': recipe_ingredient.inventory_item.type
            })

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale_factor': scale_factor,
            'ingredients': scaled_ingredients,
            'total_ingredients': len(scaled_ingredients)
        }

    except Exception as e:
        logger.error(f"Error calculating scaled ingredients for recipe {recipe_id}: {e}")
        return {'success': False, 'error': str(e)}


def validate_scaling_factor(scale_factor: float) -> tuple[bool, str]:
    """
    Validate that a scaling factor is reasonable.
    
    Args:
        scale_factor: Factor to validate
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    try:
        if scale_factor <= 0:
            return False, "Scaling factor must be positive"
        
        if scale_factor > 1000:
            return False, "Scaling factor too large (max 1000x)"
        
        if scale_factor < 0.001:
            return False, "Scaling factor too small (min 0.001x)"
        
        return True, ""

    except Exception as e:
        logger.error(f"Error validating scaling factor: {e}")
        return False, "Invalid scaling factor"
