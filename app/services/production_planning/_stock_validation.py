"""
Stock Validation via USCS

Simplified interface that delegates all stock checking to USCS.
Production planning focuses on its unique value: cost analysis and container strategy.
"""

import logging
from typing import List, Dict, Any
from flask_login import current_user

from ...models import Recipe
from ..stock_check import UniversalStockCheckService
from .types import IngredientRequirement

logger = logging.getLogger(__name__)


def validate_ingredients_with_uscs(recipe: Recipe, scale: float, organization_id: int) -> List[IngredientRequirement]:
    """
    Use USCS to validate ingredients and convert to production planning format.

    This is now a thin wrapper around USCS that converts results to IngredientRequirement objects
    for compatibility with production planning cost calculations.
    """
    try:
        # Use USCS directly - no duplication of stock check logic
        uscs = UniversalStockCheckService()
        stock_results = uscs.check_recipe_stock(recipe.id, scale)

        if not stock_results.get('success'):
            logger.error(f"USCS stock check failed: {stock_results.get('error')}")
            return []

        # Convert USCS results to IngredientRequirement objects for cost calculation
        ingredient_requirements = []

        for stock_item in stock_results.get('stock_check', []):
            # Find recipe ingredient for cost data
            recipe_ingredient = next(
                (ri for ri in recipe.recipe_ingredients if ri.inventory_item_id == stock_item['item_id']),
                None
            )

            if not recipe_ingredient:
                continue

            # Convert USCS status to production planning status
            status = _convert_uscs_status(stock_item.get('status', 'unknown'))

            requirement = IngredientRequirement(
                ingredient_id=stock_item['item_id'],
                ingredient_name=stock_item['item_name'],
                base_quantity=recipe_ingredient.quantity,
                scaled_quantity=stock_item['needed_quantity'],
                unit=stock_item['needed_unit'],
                available_quantity=stock_item['available_quantity'],
                cost_per_unit=getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0,
                total_cost=(stock_item['needed_quantity']) * (getattr(recipe_ingredient.inventory_item, 'cost_per_unit', 0) or 0),
                status=status
            )

            ingredient_requirements.append(requirement)

        return ingredient_requirements

    except Exception as e:
        logger.error(f"Error in validate_ingredients_with_uscs: {e}")
        return []


def _convert_uscs_status(uscs_status: str) -> str:
    """Convert USCS status to production planning status"""
    status_map = {
        'OK': 'available',
        'LOW': 'low', 
        'NEEDED': 'insufficient',
        'OUT_OF_STOCK': 'unavailable',
        'ERROR': 'unknown'
    }
    return status_map.get(uscs_status.upper(), 'unknown')


