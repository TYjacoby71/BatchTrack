from ..models import db, Recipe, InventoryItem
from app.services.unit_conversion import ConversionEngine
from flask_login import current_user

def universal_stock_check(recipe, scale=1.0, flex_mode=False):
    """Universal Stock Check Service (USCS) - Ingredients Only"""
    results = []
    all_ok = True

    # Check each ingredient in the recipe
    for recipe_ingredient in recipe.recipe_ingredients:
        # Get ingredient with organization scoping
        if current_user.is_authenticated and current_user.role != 'developer':
            ingredient = InventoryItem.query.filter_by(
                id=recipe_ingredient.inventory_item_id,
                organization_id=current_user.organization_id
            ).first()
        else:
            ingredient = recipe_ingredient.inventory_item
            
        if not ingredient:
            # Handle case where ingredient doesn't exist in user's organization
            results.append({
                'type': 'ingredient',
                'name': f"Item ID {recipe_ingredient.inventory_item_id}",
                'needed': recipe_ingredient.amount * scale,
                'needed_unit': recipe_ingredient.unit,
                'available': 0,
                'available_unit': recipe_ingredient.unit,
                'status': 'NOT_FOUND',
                'error': 'Ingredient not found in your organization'
            })
            all_ok = False
            continue
        needed_amount = recipe_ingredient.amount * scale

        # Get current inventory details
        available = ingredient.quantity or 0
        stock_unit = ingredient.unit
        recipe_unit = recipe_ingredient.unit
        density = ingredient.density if ingredient.density else None
        try:
            # Convert available stock to recipe unit using UUCS
            conversion_result = ConversionEngine.convert_units(
                available,
                stock_unit,
                recipe_unit,
                ingredient_id=ingredient.id
            )
            if isinstance(conversion_result, dict):
                available_converted = conversion_result['converted_value']
            else:
                raise ValueError(f"Unexpected conversion result format for {ingredient.name}")

            # Determine status
            if available_converted >= needed_amount:
                status = 'OK'
            elif available_converted >= needed_amount * 0.5:
                status = 'LOW'
                all_ok = False
            else:
                status = 'NEEDED'
                all_ok = False

            # Append result for this ingredient
            # Ensure consistent numeric formatting
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': float(needed_amount),
                'needed_unit': recipe_unit,
                'available': float(available_converted),
                'available_unit': recipe_unit,
                'raw_stock': float(available),
                'stock_unit': stock_unit,
                'status': status,
                'formatted_needed': f"{needed_amount:.2f} {recipe_unit}",
                'formatted_available': f"{available_converted:.2f} {recipe_unit}"
            })

        except ValueError as e:
            error_msg = f"Cannot convert {recipe_unit} to {stock_unit}"
            status = 'DENSITY_MISSING' if "density" in str(e).lower() else 'ERROR'
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': 0,
                'available_unit': recipe_unit,
                'status': status,
                'error': str(e)
            })
            all_ok = False

    return {
        'stock_check': results,
        'all_ok': all_ok
    }