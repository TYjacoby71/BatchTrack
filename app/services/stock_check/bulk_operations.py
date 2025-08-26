"""
Bulk Operations Module for Universal Stock Check System

Simple wrapper around USCS core bulk functions.
"""

import logging
from typing import Dict, Any, List

from .core import UniversalStockCheckService

logger = logging.getLogger(__name__)


def check_multiple_recipes(recipe_ids: List[int], scale: float = 1.0) -> Dict[str, Any]:
    """
    Check stock for multiple recipes at the same scale.

    Args:
        recipe_ids: List of recipe IDs to check
        scale: Scale factor to apply to all recipes

    Returns:
        Dictionary with results for each recipe
    """
    try:
        # Build recipe configs
        recipe_configs = [
            {'recipe_id': recipe_id, 'scale': scale}
            for recipe_id in recipe_ids
        ]

        # Use USCS bulk checking
        uscs = UniversalStockCheckService()
        return uscs.check_bulk_recipes(recipe_configs)

    except Exception as e:
        logger.error(f"Error in bulk recipe check: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def check_multiple_recipes_with_scales(recipe_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check stock for multiple recipes with different scales.

    Args:
        recipe_configs: List of dicts with keys: recipe_id, scale

    Returns:
        Dictionary with results for each recipe
    """
    try:
        # Use USCS bulk checking
        uscs = UniversalStockCheckService()
        return uscs.check_bulk_recipes(recipe_configs)

    except Exception as e:
        logger.error(f"Error in bulk recipe check with scales: {e}")
        return {
            'success': False,
            'error': str(e)
        }