"""
Recipe Validation Operations

Handles validation of recipe data, ingredients, and business rules.
"""

import logging
from typing import Any, Dict, List, Tuple

from ...extensions import db
from ...models import InventoryItem, Recipe, RecipeGroup

logger = logging.getLogger(__name__)


def _resolve_scoped_org_context(
    organization_id: int | None, recipe_id: int | None
) -> tuple[int | None, Recipe | None]:
    """Resolve organization scope and existing recipe for validation checks."""
    from flask import session
    from flask_login import current_user

    scoped_org_id = organization_id
    existing_recipe = None

    if recipe_id:
        try:
            existing_recipe = db.session.get(Recipe, recipe_id)
            if existing_recipe and scoped_org_id is None:
                scoped_org_id = existing_recipe.organization_id
        except Exception:
            existing_recipe = None

    if scoped_org_id is None:
        try:
            if getattr(current_user, "is_authenticated", False):
                if getattr(current_user, "user_type", None) == "developer":
                    scoped_org_id = session.get("dev_selected_org_id")
                else:
                    scoped_org_id = getattr(current_user, "organization_id", None)
        except Exception:
            scoped_org_id = None

    return scoped_org_id, existing_recipe


def validate_recipe_data(
    name: str,
    ingredients: List[Dict] = None,
    yield_amount: float = None,
    recipe_id: int = None,
    notes: str = None,
    category: str = None,
    tags: str = None,
    batch_size: float = None,
    portioning_data: Dict | None = None,
    allow_partial: bool = False,
    organization_id: int | None = None,
    allow_duplicate_name: bool = False,
) -> Dict[str, Any]:
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
        is_valid, error = validate_recipe_name(
            name,
            recipe_id,
            organization_id=organization_id,
            allow_duplicate_name=allow_duplicate_name,
        )
        if not is_valid:
            return {"valid": False, "error": error, "missing_fields": []}

        missing_fields: List[str] = []
        existing_recipe = None
        if recipe_id is not None:
            try:
                existing_recipe = db.session.get(Recipe, recipe_id)
            except Exception as e:
                logger.error(
                    f"Exception loading recipe {recipe_id} for validation: {e}"
                )
                existing_recipe = None

        has_direct_yield = bool(yield_amount is not None and yield_amount > 0)
        bulk_yield_ok = False
        try:
            if portioning_data and portioning_data.get("is_portioned"):
                byq = float(portioning_data.get("bulk_yield_quantity") or 0)
                bulk_yield_ok = byq > 0
        except Exception:
            bulk_yield_ok = False

        has_valid_yield = has_direct_yield or bulk_yield_ok

        if not allow_partial and not has_valid_yield:
            if existing_recipe and (existing_recipe.predicted_yield or 0) > 0:
                has_valid_yield = True

            if not has_valid_yield:
                missing_fields.append("yield amount")

        portion_requires_count = False
        portion_count_candidate = 0
        if portioning_data and portioning_data.get("is_portioned"):
            portion_requires_count = True
            try:
                portion_count_candidate = int(portioning_data.get("portion_count") or 0)
            except Exception:
                portion_count_candidate = 0
        elif existing_recipe and existing_recipe.is_portioned:
            portion_requires_count = True
            portion_count_candidate = existing_recipe.portion_count or 0

        if (
            portion_requires_count
            and not allow_partial
            and portion_count_candidate <= 0
        ):
            missing_fields.append("portion count")

        if ingredients:
            is_valid, error = validate_ingredient_quantities(ingredients)
            if not is_valid:
                return {"valid": False, "error": error, "missing_fields": []}
        elif not allow_partial:
            missing_fields.append("ingredients")

        if missing_fields:

            def _humanize(fields: List[str]) -> str:
                if not fields:
                    return ""
                if len(fields) == 1:
                    return fields[0].capitalize()
                return (
                    ", ".join(field.capitalize() for field in fields[:-1])
                    + f" and {fields[-1].capitalize()}"
                )

            pretty = _humanize(missing_fields)
            return {
                "valid": False,
                "error": f"Missing required fields: {pretty}",
                "missing_fields": missing_fields,
            }

        return {"valid": True, "error": "", "missing_fields": []}

    except Exception as e:
        logger.error(f"Error validating recipe data: {e}")
        return {
            "valid": False,
            "error": "Validation error occurred",
            "missing_fields": [],
        }


def validate_recipe_name(
    name: str,
    recipe_id: int = None,
    organization_id: int | None = None,
    *,
    allow_duplicate_name: bool = False,
) -> Tuple[bool, str]:
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
        if allow_duplicate_name:
            return True, ""

        scoped_org_id, existing_recipe = _resolve_scoped_org_context(
            organization_id, recipe_id
        )
        current_group_id = (
            getattr(existing_recipe, "recipe_group_id", None) if existing_recipe else None
        )

        # Master recipe names are unique at the recipe-group level.
        query = RecipeGroup.query.filter(RecipeGroup.name == name)
        if scoped_org_id is not None:
            query = query.filter(RecipeGroup.organization_id == scoped_org_id)
        if current_group_id:
            query = query.filter(RecipeGroup.id != current_group_id)

        existing_group = query.first()
        if existing_group:
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
            if "item_id" not in ingredient:
                return False, f"Ingredient {i+1}: item_id is required"

            if "quantity" not in ingredient:
                return False, f"Ingredient {i+1}: quantity is required"

            if "unit" not in ingredient:
                return False, f"Ingredient {i+1}: unit is required"

            item_id = ingredient["item_id"]
            quantity = ingredient["quantity"]

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
            if item.type not in ["ingredient", "container"]:
                return False, f"{item.name} is not a valid ingredient type"

        return True, ""

    except Exception as e:
        logger.error(f"Error validating ingredient quantities: {e}")
        return False, "Ingredient validation error"
