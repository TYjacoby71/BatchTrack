
"""
Core Recipe Operations

Handles the fundamental CRUD operations for recipes.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models import Recipe, RecipeIngredient, InventoryItem
from ._validation import validate_recipe_data

logger = logging.getLogger(__name__)


def create_recipe(name: str, description: str = None, instructions: str = None, 
                 yield_amount: float = 1.0, yield_unit: str = 'piece',
                 ingredients: List[Dict] = None, created_by: int = None,
                 organization_id: int = None) -> tuple[bool, Any]:
    """
    Create a new recipe with ingredients.
    
    Args:
        name: Recipe name
        description: Recipe description
        instructions: Recipe instructions
        yield_amount: Amount produced by recipe
        yield_unit: Unit of yield
        ingredients: List of ingredient dicts with item_id, quantity, unit
        created_by: User ID creating the recipe
        organization_id: Organization ID
        
    Returns:
        Tuple of (success: bool, recipe_or_error_message)
    """
    try:
        # Validate input data
        is_valid, validation_error = validate_recipe_data(
            name=name,
            ingredients=ingredients or [],
            yield_amount=yield_amount
        )
        if not is_valid:
            return False, validation_error

        # Create recipe
        recipe = Recipe(
            name=name,
            description=description,
            instructions=instructions,
            yield_amount=yield_amount,
            yield_unit=yield_unit,
            created_by=created_by or current_user.id,
            organization_id=organization_id or current_user.organization_id
        )
        
        db.session.add(recipe)
        db.session.flush()  # Get recipe ID

        # Add ingredients
        if ingredients:
            success, error = _add_recipe_ingredients(recipe.id, ingredients)
            if not success:
                db.session.rollback()
                return False, error

        db.session.commit()
        logger.info(f"Created recipe {recipe.name} (ID: {recipe.id})")
        return True, recipe

    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Recipe name conflict: {e}")
        return False, "Recipe name already exists"
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating recipe: {e}")
        return False, str(e)


def update_recipe(recipe_id: int, name: str = None, description: str = None,
                 instructions: str = None, yield_amount: float = None,
                 yield_unit: str = None, ingredients: List[Dict] = None) -> tuple[bool, Any]:
    """
    Update an existing recipe.
    
    Args:
        recipe_id: Recipe to update
        name: New recipe name
        description: New description
        instructions: New instructions
        yield_amount: New yield amount
        yield_unit: New yield unit
        ingredients: New ingredient list (replaces existing)
        
    Returns:
        Tuple of (success: bool, recipe_or_error_message)
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return False, "Recipe not found"

        # Update fields if provided
        if name is not None:
            recipe.name = name
        if description is not None:
            recipe.description = description
        if instructions is not None:
            recipe.instructions = instructions
        if yield_amount is not None:
            recipe.yield_amount = yield_amount
        if yield_unit is not None:
            recipe.yield_unit = yield_unit

        # Update ingredients if provided
        if ingredients is not None:
            # Remove existing ingredients
            RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()
            
            # Add new ingredients
            success, error = _add_recipe_ingredients(recipe_id, ingredients)
            if not success:
                db.session.rollback()
                return False, error

        db.session.commit()
        logger.info(f"Updated recipe {recipe.name} (ID: {recipe.id})")
        return True, recipe

    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Recipe update conflict: {e}")
        return False, "Recipe name already exists"
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating recipe: {e}")
        return False, str(e)


def delete_recipe(recipe_id: int) -> tuple[bool, str]:
    """
    Delete a recipe and its ingredients.
    
    Args:
        recipe_id: Recipe to delete
        
    Returns:
        Tuple of (success: bool, message)
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return False, "Recipe not found"

        recipe_name = recipe.name
        
        # Delete ingredients first (foreign key constraint)
        RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()
        
        # Delete recipe
        db.session.delete(recipe)
        db.session.commit()
        
        logger.info(f"Deleted recipe {recipe_name} (ID: {recipe_id})")
        return True, "Recipe deleted successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting recipe: {e}")
        return False, str(e)


def get_recipe_details(recipe_id: int) -> Optional[Recipe]:
    """Get recipe with full ingredient details."""
    try:
        return Recipe.query.options(
            db.joinedload(Recipe.ingredients).joinedload(RecipeIngredient.inventory_item)
        ).get(recipe_id)
    except Exception as e:
        logger.error(f"Error getting recipe details: {e}")
        return None


def duplicate_recipe(recipe_id: int, new_name: str = None) -> tuple[bool, Any]:
    """
    Duplicate an existing recipe.
    
    Args:
        recipe_id: Recipe to duplicate
        new_name: Name for new recipe (or auto-generate)
        
    Returns:
        Tuple of (success: bool, new_recipe_or_error_message)
    """
    try:
        original = get_recipe_details(recipe_id)
        if not original:
            return False, "Original recipe not found"

        # Generate new name if not provided
        if not new_name:
            new_name = f"{original.name} (Copy)"

        # Prepare ingredient data
        ingredients = []
        for ingredient in original.ingredients:
            ingredients.append({
                'item_id': ingredient.inventory_item_id,
                'quantity': ingredient.quantity,
                'unit': ingredient.unit
            })

        # Create duplicate
        return create_recipe(
            name=new_name,
            description=original.description,
            instructions=original.instructions,
            yield_amount=original.yield_amount,
            yield_unit=original.yield_unit,
            ingredients=ingredients
        )

    except Exception as e:
        logger.error(f"Error duplicating recipe: {e}")
        return False, str(e)


def _add_recipe_ingredients(recipe_id: int, ingredients: List[Dict]) -> tuple[bool, str]:
    """
    Add ingredients to a recipe.
    
    Args:
        recipe_id: Recipe to add ingredients to
        ingredients: List of ingredient dicts
        
    Returns:
        Tuple of (success: bool, error_message_or_none)
    """
    try:
        for ingredient_data in ingredients:
            # Validate ingredient exists
            item = InventoryItem.query.get(ingredient_data['item_id'])
            if not item:
                return False, f"Ingredient {ingredient_data['item_id']} not found"

            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe_id,
                inventory_item_id=ingredient_data['item_id'],
                quantity=ingredient_data['quantity'],
                unit=ingredient_data['unit']
            )
            db.session.add(recipe_ingredient)

        return True, None

    except Exception as e:
        logger.error(f"Error adding recipe ingredients: {e}")
        return False, str(e)
