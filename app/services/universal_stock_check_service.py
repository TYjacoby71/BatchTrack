
"""
Universal Stock Check Service (USCS)

This is the canonical, single-source-of-truth for all stock availability checking
across the application. It orchestrates FIFO inventory, unit conversions, and 
cross-domain availability validation.

Used by:
- Recipe planning
- Batch production
- Bulk stock checks  
- Product/Shopify integration (future)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from ..extensions import db
from ..models import Recipe, RecipeIngredient, InventoryItem
from ..blueprints.fifo.services import FIFOService
from ..services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)


def check_recipe_availability(recipe_id: int, scale_factor: float = 1.0) -> Dict[str, Any]:
    """
    Universal stock check for recipe availability.
    
    Args:
        recipe_id: Recipe to check
        scale_factor: Scaling factor for recipe
        
    Returns:
        Dict with availability results
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {
                'success': False,
                'error': 'Recipe not found',
                'can_make': False
            }

        availability_results = []
        all_available = True
        
        for recipe_ingredient in recipe.recipe_ingredients:
            ingredient_result = check_ingredient_availability(
                recipe_ingredient.inventory_item_id,
                recipe_ingredient.quantity * scale_factor,
                recipe_ingredient.unit
            )
            
            if not ingredient_result['available']:
                all_available = False
                
            availability_results.append({
                'ingredient_id': recipe_ingredient.inventory_item_id,
                'ingredient_name': recipe_ingredient.inventory_item.name,
                'required_quantity': recipe_ingredient.quantity * scale_factor,
                'required_unit': recipe_ingredient.unit,
                'is_available': ingredient_result['available'],
                'available_quantity': ingredient_result['available_quantity'],
                'shortage': ingredient_result['shortage']
            })

        return {
            'success': True,
            'recipe_id': recipe_id,
            'scale_factor': scale_factor,
            'can_make': all_available,
            'ingredients': availability_results
        }

    except Exception as e:
        logger.error(f"Error checking recipe availability: {e}")
        return {
            'success': False,
            'error': str(e),
            'can_make': False
        }


def check_ingredient_availability(ingredient_id: int, required_amount: float, 
                                unit: str) -> Dict[str, Any]:
    """
    Check availability of a single ingredient.
    
    Args:
        ingredient_id: Ingredient to check
        required_amount: Amount needed
        unit: Unit of measurement
        
    Returns:
        Dict with availability details
    """
    try:
        ingredient = InventoryItem.query.get(ingredient_id)
        if not ingredient:
            return {
                'available': False,
                'available_quantity': 0,
                'shortage': required_amount,
                'error': 'Ingredient not found'
            }

        # Get available FIFO entries (non-expired only)
        available_entries = FIFOService.get_fifo_entries(ingredient_id)
        
        # Convert to ingredient's base unit for accurate calculation
        conversion_engine = ConversionEngine()
        try:
            converted_required = conversion_engine.convert_to_base_unit(
                required_amount, unit, ingredient_id
            )
        except Exception as e:
            logger.warning(f"Unit conversion failed for {ingredient.name}: {e}")
            # Fallback: assume same unit
            converted_required = required_amount

        # Calculate total available in base units
        total_available = sum(entry.remaining_quantity for entry in available_entries)
        
        # Check availability
        is_available = total_available >= converted_required
        shortage = max(0, converted_required - total_available)

        return {
            'available': is_available,
            'available_quantity': total_available,
            'shortage': shortage,
            'ingredient_name': ingredient.name
        }

    except Exception as e:
        logger.error(f"Error checking ingredient availability: {e}")
        return {
            'available': False,
            'available_quantity': 0,
            'shortage': required_amount,
            'error': str(e)
        }


def bulk_stock_check(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform bulk stock availability check.
    
    Args:
        items: List of items to check with ingredient_id, quantity, unit
        
    Returns:
        Dict with bulk check results
    """
    try:
        results = []
        
        for item in items:
            result = check_ingredient_availability(
                item['ingredient_id'],
                item['quantity'],
                item['unit']
            )
            result['requested_quantity'] = item['quantity']
            result['requested_unit'] = item['unit']
            results.append(result)

        all_available = all(result['available'] for result in results)
        
        return {
            'success': True,
            'all_available': all_available,
            'items': results,
            'checked_at': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in bulk stock check: {e}")
        return {
            'success': False,
            'error': str(e),
            'items': []
        }


def get_available_inventory_summary() -> Dict[str, Any]:
    """
    Get summary of all available inventory.
    
    Returns:
        Dict with inventory summary
    """
    try:
        summary = {}
        
        # Get all active ingredients
        ingredients = InventoryItem.query.filter(
            InventoryItem.type.in_(['ingredient', 'container'])
        ).all()
        
        for ingredient in ingredients:
            # Get available FIFO entries
            available_entries = FIFOService.get_fifo_entries(ingredient.id)
            total_available = sum(entry.remaining_quantity for entry in available_entries)
            
            summary[ingredient.id] = {
                'name': ingredient.name,
                'available_quantity': total_available,
                'unit': ingredient.unit,
                'last_updated': datetime.utcnow().isoformat()
            }

        return {
            'success': True,
            'summary': summary,
            'generated_at': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating inventory summary: {e}")
        return {
            'success': False,
            'error': str(e),
            'summary': {}
        }


def _fresh_filter(model):
    """Filter for non-expired inventory items."""
    return model.query.filter(
        model.expiration_date.is_(None) | 
        (model.expiration_date > datetime.utcnow())
    )
