"""
Recipe Core Operations

Handles CRUD operations for recipes with proper service integration.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from flask_login import current_user

from ...models import Recipe, RecipeIngredient, InventoryItem
from ...models.recipe import RecipeConsumable
from ...extensions import db
from ._validation import validate_recipe_data
from ...utils.code_generator import generate_recipe_prefix
from ...services.event_emitter import EventEmitter

logger = logging.getLogger(__name__)


def create_recipe(name: str, description: str = "", instructions: str = "",
                 yield_amount: float = 0.0, yield_unit: str = "",
                 ingredients: List[Dict] = None, parent_id: int = None,
                 allowed_containers: List[int] = None, label_prefix: str = "",
                 consumables: List[Dict] = None) -> Tuple[bool, Any]:
    """
    Create a new recipe with ingredients and UI fields.

    Args:
        name: Recipe name
        description: Recipe description  
        instructions: Cooking instructions
        yield_amount: Expected yield quantity
        yield_unit: Unit for yield
        ingredients: List of ingredient dicts with item_id, quantity, unit
        parent_id: Parent recipe ID for variations
        allowed_containers: List of container IDs
        label_prefix: Label prefix for batches

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        # Validate input data
        validation_result = validate_recipe_data(
            name=name,
            ingredients=ingredients or [],
            yield_amount=yield_amount
        )

        if not validation_result['valid']:
            return False, validation_result['error']

        # Create recipe with proper label prefix
        final_label_prefix = label_prefix
        if not final_label_prefix:
            # Generate prefix from recipe name if not provided
            final_label_prefix = generate_recipe_prefix(name)
            
            # For variations, ensure unique prefix
            if parent_id:
                parent_recipe = Recipe.query.get(parent_id)
                if parent_recipe and parent_recipe.label_prefix:
                    # Use parent prefix with variation suffix
                    base_prefix = parent_recipe.label_prefix
                    # Check for existing variations with same base prefix
                    existing_variations = Recipe.query.filter(
                        Recipe.parent_id == parent_id,
                        Recipe.label_prefix.like(f"{base_prefix}%")
                    ).count()
                    if existing_variations > 0:
                        final_label_prefix = f"{base_prefix}V{existing_variations + 1}"
                    else:
                        final_label_prefix = f"{base_prefix}V1"

        recipe = Recipe(
            name=name,
            instructions=instructions,
            predicted_yield=yield_amount,
            predicted_yield_unit=yield_unit,
            organization_id=current_user.organization_id,
            parent_id=parent_id,
            label_prefix=final_label_prefix
        )

        # Set allowed containers
        if allowed_containers:
            recipe.allowed_containers = allowed_containers

        db.session.add(recipe)
        db.session.flush()  # Get recipe ID

        # Add ingredients
        for ingredient_data in ingredients or []:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                inventory_item_id=ingredient_data['item_id'],
                quantity=ingredient_data['quantity'],
                unit=ingredient_data['unit']
            )
            db.session.add(recipe_ingredient)

        # Add consumables
        for consumable in consumables or []:
            recipe_consumable = RecipeConsumable(
                recipe_id=recipe.id,
                inventory_item_id=consumable['item_id'],
                quantity=consumable['quantity'],
                unit=consumable['unit']
            )
            db.session.add(recipe_consumable)

        db.session.commit()
        logger.info(f"Created recipe {recipe.id}: {name}")

        # Emit recipe_created
        try:
            EventEmitter.emit(
                event_name='recipe_created',
                properties={'name': name, 'yield_amount': yield_amount, 'yield_unit': yield_unit},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe.id
            )
        except Exception:
            pass

        return True, recipe

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating recipe: {e}")
        return False, str(e)


def update_recipe(recipe_id: int, name: str = None, description: str = None,
                 instructions: str = None, yield_amount: float = None,
                 yield_unit: str = None, ingredients: List[Dict] = None,
                 allowed_containers: List[int] = None, label_prefix: str = None,
                 consumables: List[Dict] = None) -> Tuple[bool, Any]:
    """
    Update an existing recipe.

    Args:
        recipe_id: Recipe to update
        name: New name (optional)
        description: New description (optional)
        instructions: New instructions (optional)
        yield_amount: New yield amount (optional)
        yield_unit: New yield unit (optional)
        ingredients: New ingredients list (optional)
        allowed_containers: New container list (optional)
        label_prefix: New label prefix (optional)

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return False, "Recipe not found"

        if recipe.is_locked:
            return False, "Recipe is locked and cannot be modified"

        # Update basic fields
        if name is not None:
            # Validate name uniqueness for updates
            validation_result = validate_recipe_data(
                name=name,
                recipe_id=recipe_id
            )
            if not validation_result['valid']:
                return False, validation_result['error']
            recipe.name = name
        if instructions is not None:
            recipe.instructions = instructions
        if yield_amount is not None:
            recipe.predicted_yield = yield_amount
        if yield_unit is not None:
            recipe.predicted_yield_unit = yield_unit
        if label_prefix is not None:
            recipe.label_prefix = label_prefix
        if allowed_containers is not None:
            recipe.allowed_containers = allowed_containers

        # Update ingredients if provided
        if ingredients is not None:
            # Validate new ingredients
            validation_result = validate_recipe_data(
                name=recipe.name,
                ingredients=ingredients,
                yield_amount=recipe.predicted_yield,
                recipe_id=recipe_id
            )

            if not validation_result['valid']:
                return False, validation_result['error']

            # Remove existing ingredients
            RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()

            # Add new ingredients
            for ingredient_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    inventory_item_id=ingredient_data['item_id'],
                    quantity=ingredient_data['quantity'],
                    unit=ingredient_data['unit']
                )
                db.session.add(recipe_ingredient)

        # Update consumables if provided
        if consumables is not None:
            from ...models.recipe import RecipeConsumable
            RecipeConsumable.query.filter_by(recipe_id=recipe_id).delete()
            for item in consumables:
                db.session.add(RecipeConsumable(
                    recipe_id=recipe.id,
                    inventory_item_id=item['item_id'],
                    quantity=item['quantity'],
                    unit=item['unit']
                ))

        db.session.commit()
        logger.info(f"Updated recipe {recipe_id}: {recipe.name}")

        # Emit recipe_updated
        try:
            EventEmitter.emit(
                event_name='recipe_updated',
                properties={'recipe_id': recipe_id},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe.id
            )
        except Exception:
            pass

        return True, recipe

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating recipe {recipe_id}: {e}")
        return False, str(e)


def delete_recipe(recipe_id: int) -> Tuple[bool, str]:
    """
    Delete a recipe and its ingredients.

    Args:
        recipe_id: Recipe to delete

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return False, "Recipe not found"

        if recipe.is_locked:
            return False, "Recipe is locked and cannot be deleted"

        # Check for active batches
        from ...models.batch import Batch
        active_batches = Batch.query.filter_by(
            recipe_id=recipe_id, 
            status='in_progress'
        ).count()

        if active_batches > 0:
            return False, "Cannot delete recipe with active batches"

        recipe_name = recipe.name

        # Delete ingredients first (foreign key constraint)
        RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()

        # Delete recipe
        db.session.delete(recipe)
        db.session.commit()

        logger.info(f"Deleted recipe {recipe_id}: {recipe_name}")
        # Emit recipe_deleted
        try:
            EventEmitter.emit(
                event_name='recipe_deleted',
                properties={'name': recipe_name},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe_id
            )
        except Exception:
            pass
        return True, f"Recipe '{recipe_name}' deleted successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting recipe {recipe_id}: {e}")
        return False, f"Error deleting recipe: {str(e)}"


def get_recipe_details(recipe_id: int) -> Optional[Recipe]:
    """
    Get detailed recipe information with all relationships loaded.

    Args:
        recipe_id: ID of the recipe to retrieve

    Returns:
        Recipe object with relationships loaded, or None if not found

    Raises:
        ValueError: If recipe_id is invalid
        PermissionError: If user doesn't have access to recipe
    """
    if not recipe_id or recipe_id <= 0:
        raise ValueError("Invalid recipe ID")

    try:
        from sqlalchemy.orm import joinedload

        from ...models import RecipeIngredient, RecipeConsumable, InventoryItem
        
        recipe = db.session.query(Recipe).options(
            joinedload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.inventory_item),
            joinedload(Recipe.recipe_consumables).joinedload(RecipeConsumable.inventory_item)
        ).filter(Recipe.id == recipe_id).first()

        if not recipe:
            return None

        # Check organization access
        if current_user.organization_id and recipe.organization_id != current_user.organization_id:
            raise PermissionError("Access denied to recipe")

        return recipe

    except Exception as e:
        logger.error(f"Error retrieving recipe {recipe_id}: {str(e)}")
        raise


def duplicate_recipe(recipe_id: int) -> Tuple[bool, Any]:
    """
    Create a copy of an existing recipe.

    Args:
        recipe_id: Recipe to duplicate

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        original = get_recipe_details(recipe_id)
        if not original:
            return False, "Original recipe not found"

        # Extract ingredient data
        ingredients = [
            {
                'item_id': ri.inventory_item_id,
                'quantity': ri.quantity,
                'unit': ri.unit
            }
            for ri in original.recipe_ingredients
        ]

        # Extract consumable data
        consumables = [
            {
                'item_id': rc.inventory_item_id,
                'quantity': rc.quantity,
                'unit': rc.unit
            }
            for rc in original.recipe_consumables
        ]

        # Generate new prefix for clone (don't reuse original prefix)
        clone_name = f"{original.name} (Copy)"
        clone_prefix = generate_recipe_prefix(clone_name)

        # Create new recipe
        return create_recipe(
            name=clone_name,
            description=original.instructions,
            instructions=original.instructions,
            yield_amount=original.predicted_yield or 0.0,
            yield_unit=original.predicted_yield_unit or "",
            ingredients=ingredients,
            consumables=consumables,
            allowed_containers=getattr(original, 'allowed_containers', []),
            label_prefix=clone_prefix
        )

    except Exception as e:
        logger.error(f"Error duplicating recipe {recipe_id}: {e}")
        return False, str(e)