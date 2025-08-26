"""
Recipe Stock Checking Operations

Simple wrapper around USCS core functions.
"""

import logging
from typing import Dict, Any

from ..stock_check.core import UniversalStockCheckService

logger = logging.getLogger(__name__)


def check_recipe_stock(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Check stock for all ingredients in a recipe using USCS.

    Args:
        recipe_id: Recipe ID
        scale: Scale factor for the recipe

    Returns:
        Dictionary with stock check results
    """
    try:
        uscs = UniversalStockCheckService()
        return uscs.check_recipe_stock(recipe_id, scale)

    except Exception as e:
        logger.error(f"Error in check_recipe_stock: {e}")
        return {
            'success': False,
            'status': 'error',
            'stock_check': [],
            'error': str(e)
        }