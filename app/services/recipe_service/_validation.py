"""
Recipe Validation Operations

Handles validation of recipe data, ingredients, and business rules.
"""

import logging
from typing import Dict, Any, List, Tuple

from ...extensions import db
from ...models import InventoryItem, Recipe

logger = logging.getLogger(__name__)


def validate_recipe_data(name: str, ingredients: List[Dict] = None, 
                        yield_amount: float = None, recipe_id: int = None, notes: str = None, category: str = None, tags: str = None, batch_size: float = None,
                        portioning_data: Dict | None = None) -> Dict[str, Any]:
    """
    Validate recipe data before creation or update.

    Args:
        name: Recipe name
        ingredients: List of ingredient dicts
        yield_amount: Recipe yield amount
        recipe_id: Current recipe ID (for updates)
        notes: Recipe notes
        category: Recipe category
        tags: Recipe tags
        batch_size: Recipe batch size

    Returns:
        Dict with 'valid' (bool) and 'error' (str) keys
    """
    try:
        # Validate name - pass recipe_id for edit validation
        is_valid, error = validate_recipe_name(name, recipe_id)
        if not is_valid:
            return {'valid': False, 'error': error}

        # DEBUG: Add comprehensive yield validation debugging
        logger.info(f"=== YIELD VALIDATION DEBUG ===")
        logger.info(f"yield_amount: {yield_amount} (type: {type(yield_amount)})")
        logger.info(f"recipe_id: {recipe_id}")
        logger.info(f"portioning_data: {portioning_data}")

        # Validate yield amount: must be > 0 for regular recipes, or bulk yield > 0 for portioned recipes
        # For existing recipes (recipe_id is provided), be more lenient with yield validation
        if yield_amount is not None and yield_amount > 0:
            logger.info("✅ Valid yield amount provided directly")
            pass
        elif recipe_id is not None:
            logger.info("🔍 Checking existing recipe for yield validation")
            # For recipe edits, check if the existing recipe has a valid yield
            # This allows editing existing recipes without requiring yield changes
            try:
                existing_recipe = db.session.get(Recipe, recipe_id)
                logger.info(f"Existing recipe found: {existing_recipe is not None}")
                if existing_recipe:
                    logger.info(f"Existing recipe yield: {existing_recipe.predicted_yield}")

                if existing_recipe and (existing_recipe.predicted_yield or 0) > 0:
                    logger.info("✅ Existing recipe has valid yield, allowing edit")
                    pass
                else:
                    logger.info("⚠️ Existing recipe has no valid yield, checking bulk yield")
                    # Check bulk yield for portioned recipes
                    bulk_ok = False
                    try:
                        if portioning_data and portioning_data.get('is_portioned'):
                            byq = float(portioning_data.get('bulk_yield_quantity') or 0)
                            logger.info(f"Bulk yield quantity: {byq}")
                            bulk_ok = byq > 0
                        logger.info(f"Bulk yield OK: {bulk_ok}")
                    except Exception as e:
                        logger.info(f"Exception checking bulk yield: {e}")
                        bulk_ok = False

                    if not bulk_ok:
                        logger.error("❌ No valid yield found - failing validation")
                        return {'valid': False, 'error': "Yield amount must be positive"}
                    else:
                        logger.info("✅ Bulk yield is valid")
            except Exception as e:
                logger.error(f"Exception checking existing recipe: {e}")
                # If we can't check existing recipe, apply normal validation
                return {'valid': False, 'error': "Yield amount must be positive"}
        else:
            logger.info("🆕 New recipe creation - strict validation required")
            # New recipe creation - strict validation required
            # Check if this is a portioned recipe with bulk yield
            bulk_ok = False
            try:
                if portioning_data and portioning_data.get('is_portioned'):
                    byq = float(portioning_data.get('bulk_yield_quantity') or 0)
                    logger.info(f"Bulk yield quantity: {byq}")
                    bulk_ok = byq > 0
                logger.info(f"Bulk yield OK: {bulk_ok}")
            except Exception as e:
                logger.info(f"Exception checking bulk yield: {e}")
                bulk_ok = False

            if not bulk_ok:
                logger.error("❌ No valid yield found - failing validation")
                return {'valid': False, 'error': "Yield amount must be positive"}
            else:
                logger.info("✅ Bulk yield is valid")

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

        # Filter by organization when available
        try:
            if getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'organization_id', None):
                query = query.filter_by(organization_id=current_user.organization_id)
        except Exception:
            # If current_user is unavailable in context, skip org scoping for validation
            pass

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
            item = db.session.get(InventoryItem, item_id)
            if not item:
                return False, f"Ingredient {item_id} not found"

            # Check if it's actually an ingredient
            if item.type not in ['ingredient', 'container']:
                return False, f"{item.name} is not a valid ingredient type"

        return True, ""

    except Exception as e:
        logger.error(f"Error validating ingredient quantities: {e}")
        return False, "Ingredient validation error"