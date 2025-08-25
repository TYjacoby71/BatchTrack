
"""
Bulk Operations Module for Universal Stock Check System

Handles bulk stock checking for multiple recipes with different scales.
This is internal to USCS and should not be exposed via API routes.
"""

import logging
from typing import Dict, Any, List
from flask_login import current_user

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
        organization_id = current_user.organization_id if current_user.is_authenticated else None

        # Build recipe configs
        recipe_configs = [
            {
                'recipe_id': recipe_id,
                'scale': scale,
                'organization_id': organization_id
            }
            for recipe_id in recipe_ids
        ]

        # Use USCS bulk recipe checking
        uscs = UniversalStockCheckService()
        return uscs.check_multiple_recipes(recipe_configs)

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
        organization_id = current_user.organization_id if current_user.is_authenticated else None

        # Add organization_id to configs
        for config in recipe_configs:
            config['organization_id'] = organization_id

        # Use USCS bulk recipe checking
        uscs = UniversalStockCheckService()
        return uscs.check_multiple_recipes(recipe_configs)

    except Exception as e:
        logger.error(f"Error in bulk recipe check with scales: {e}")
        return {
            'success': False,
            'error': str(e)
        }
