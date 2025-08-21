
"""
Recipe Validation Operations

Handles validation of recipe data, ingredients, and business rules.
"""

import logging
from typing import Dict, Any, List, Tuple

from ...models import Recipe, InventoryItem

logger = logging.getLogger(__name__)


def validate_recipe_data(name: str, ingredients: List[Dict] = None, 
                        yield_amount: float = None, recipe_id: int = None, **kwargs) -> Dict[str, Any]:
    """
    Validate recipe data before creation or update.
    
    Args:
        name: Recipe name
        ingredients: List of ingredient dicts
        yield_amount: Recipe yield amount
        recipe_id: Current recipe ID (for updates)
        **kwargs: Additional recipe fields
        
    Returns:
        Dict with 'valid' (bool) and 'error' (str) keys
    """
    try:
        # Validate name - pass recipe_id for edit validation
        is_valid, error = validate_recipe_name(name, recipe_id)
        if not is_valid:
            return {'valid': False, 'error': error}

        # Validate yield amount
        if yield_amount is not None and yield_amount <= 0:
            return {'valid': False, 'error': "Yield amount must be positive"}

        # Validate ingredients if provided
        if ingredients:
            is_valid, error = validate_ingredient_quantities(ingredients)
            if not is_valid:
                return {'valid': False, 'error': error}

        return {'valid': True, 'error': ''}

    except Exception as e:
        logger.error(f"Error validating recipe data: {e}")
        return {'valid': False, 'error': "Validation error occurred"}


def validate_recipe_name(name: str, recipe_id: int = None) -> Tuple[bool, str]:
    """
    Validate recipe name for uniqueness and format.
    
    Args:
        name: Recipe name to validate
        recipe_id: Current recipe ID (for updates)
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    try:
        if not name or not name.strip():
            return False, "Recipe name is required"
        
        name = name.strip()
        
        if len(name) < 2:
            return False, "Recipe name must be at least 2 characters"
        
        if len(name) > 100:
            return False, "Recipe name must be less than 100 characters"

        # Check for uniqueness - exclude current recipe if editing
        from flask_login import current_user
        query = Recipe.query.filter_by(name=name)
        
        # Filter by organization
        if current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)
        
        # Exclude current recipe when editing
        if recipe_id:
            query = query.filter(Recipe.id != recipe_id)
        
        existing = query.first()
        if existing:
            return False, "Recipe name already exists"

        return True, ""

    except Exception as e:
        logger.error(f"Error validating recipe name: {e}")
        return False, "Name validation error"


def validate_ingredient_quantities(ingredients: List[Dict]) -> Tuple[bool, str]:
    """
    Validate ingredient quantities and availability.
    
    Args:
        ingredients: List of ingredient dicts with item_id, quantity, unit
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    try:
        if not ingredients:
            return False, "Recipe must have at least one ingredient"

        seen_ingredients = set()
        
        for i, ingredient in enumerate(ingredients):
            # Check required fields
            if 'item_id' not in ingredient:
                return False, f"Ingredient {i+1}: item_id is required"
            
            if 'quantity' not in ingredient:
                return False, f"Ingredient {i+1}: quantity is required"
            
            if 'unit' not in ingredient:
                return False, f"Ingredient {i+1}: unit is required"

            item_id = ingredient['item_id']
            quantity = ingredient['quantity']
            
            # Check for duplicates
            if item_id in seen_ingredients:
                return False, f"Duplicate ingredient: {item_id}"
            seen_ingredients.add(item_id)

            # Validate quantity
            try:
                quantity = float(quantity)
                if quantity <= 0:
                    return False, f"Ingredient {i+1}: quantity must be positive"
            except (ValueError, TypeError):
                return False, f"Ingredient {i+1}: invalid quantity"

            # Check if ingredient exists
            item = InventoryItem.query.get(item_id)
            if not item:
                return False, f"Ingredient {item_id} not found"
            
            # Check if it's actually an ingredient
            if item.type not in ['ingredient', 'container']:
                return False, f"{item.name} is not a valid ingredient type"

        return True, ""

    except Exception as e:
        logger.error(f"Error validating ingredient quantities: {e}")
        return False, "Ingredient validation error"
