
"""
Stock Validation via USCS

Handles all stock checking logic by integrating with the Universal Stock Check Service.
Validates ingredient availability and formats results for production planning.
"""

import logging
from typing import List
from flask_login import current_user

from ...models import Recipe, RecipeIngredient
from ..stock_check import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory
from .types import IngredientRequirement

logger = logging.getLogger(__name__)


def validate_ingredients_with_uscs(recipe: Recipe, scale: float, organization_id: int) -> List[IngredientRequirement]:
    """
    Use USCS to validate all ingredient availability for a recipe.
    
    Returns list of IngredientRequirement objects with availability status.
    """
    try:
        logger.info(f"STOCK_VALIDATION: Checking ingredients for recipe {recipe.id} at scale {scale}")
        
        # Build USCS requests for all recipe ingredients
        stock_requests = []
        for recipe_ingredient in recipe.recipe_ingredients:
            request = StockCheckRequest(
                item_id=recipe_ingredient.inventory_item_id,
                quantity_needed=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                category=InventoryCategory.INGREDIENT,
                organization_id=organization_id,
                scale_factor=scale
            )
            stock_requests.append(request)
        
        # Execute bulk stock check
        uscs = UniversalStockCheckService()
        stock_results = uscs.check_bulk_items(stock_requests)
        
        # Convert results to IngredientRequirement objects
        ingredient_requirements = []
        
        for result in stock_results:
            # Find corresponding recipe ingredient for base quantity
            recipe_ingredient = next(
                (ri for ri in recipe.recipe_ingredients if ri.inventory_item_id == result.item_id),
                None
            )
            
            if not recipe_ingredient:
                logger.warning(f"Could not find recipe ingredient for item {result.item_id}")
                continue
            
            # Determine availability status
            status = _determine_availability_status(result)
            
            requirement = IngredientRequirement(
                ingredient_id=result.item_id,
                ingredient_name=result.item_name or 'Unknown',
                base_quantity=recipe_ingredient.quantity,
                scaled_quantity=recipe_ingredient.quantity * scale,
                unit=recipe_ingredient.unit,
                available_quantity=result.available_quantity or 0,
                cost_per_unit=getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0,
                total_cost=(recipe_ingredient.quantity * scale) * (getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0),
                status=status
            )
            
            ingredient_requirements.append(requirement)
        
        logger.info(f"STOCK_VALIDATION: Validated {len(ingredient_requirements)} ingredients")
        return ingredient_requirements
        
    except Exception as e:
        logger.error(f"Error validating ingredients with USCS: {e}")
        raise


def _determine_availability_status(stock_result) -> str:
    """Determine availability status from USCS result"""
    if hasattr(stock_result, 'status'):
        uscs_status = stock_result.status.upper()
        
        # Map USCS statuses to production planning statuses
        if uscs_status in ['OK', 'AVAILABLE']:
            return 'available'
        elif uscs_status == 'LOW':
            return 'low'
        elif uscs_status in ['INSUFFICIENT', 'UNAVAILABLE']:
            return 'insufficient'
        else:
            return 'unknown'
    
    # Fallback to quantity comparison
    needed = getattr(stock_result, 'needed_quantity', 0) or 0
    available = getattr(stock_result, 'available_quantity', 0) or 0
    
    if available >= needed:
        return 'available'
    elif available > 0:
        return 'insufficient'  # Some available but not enough
    else:
        return 'unavailable'  # None available


def validate_ingredient_availability(recipe_id: int, scale: float = 1.0):
    """
    Legacy compatibility function for ingredient availability checking.
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}
        
        organization_id = current_user.organization_id if current_user.is_authenticated else None
        requirements = validate_ingredients_with_uscs(recipe, scale, organization_id)
        
        # Convert to legacy format
        ingredients = []
        for req in requirements:
            ingredients.append({
                'item_id': req.ingredient_id,
                'item_name': req.ingredient_name,
                'needed_quantity': req.scaled_quantity,
                'available_quantity': req.available_quantity,
                'unit': req.unit,
                'status': req.status,
                'category': 'ingredient'
            })
        
        all_available = all(req.status in ['available', 'low'] for req in requirements)
        
        return {
            'success': True,
            'all_available': all_available,
            'ingredients': ingredients,
            'recipe_id': recipe_id,
            'scale': scale
        }
        
    except Exception as e:
        logger.error(f"Error in ingredient availability check: {e}")
        return {'success': False, 'error': str(e)}
