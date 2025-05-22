from models import db, Recipe, InventoryItem
from services.unit_conversion import ConversionEngine

def universal_stock_check(recipe, scale=1.0, flex_mode=False):
    """Universal Stock Check Service (USCS) - Ingredients Only"""
    results = []
    all_ok = True

    # Check each ingredient in the recipe
    for recipe_ingredient in recipe.recipe_ingredients:
        ingredient = recipe_ingredient.inventory_item
        needed_amount = recipe_ingredient.amount * scale

        # Get current inventory details
        available = ingredient.quantity or 0
        stock_unit = ingredient.unit
        recipe_unit = recipe_ingredient.unit
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
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': available_converted,
                'available_unit': recipe_unit,
                'raw_stock': available,
                'stock_unit': stock_unit,
                'status': status
            })

        except ValueError as e:
            error_msg = f"Cannot convert {recipe_unit} to {stock_unit}"
            if "density" in str(e).lower():
                error_msg = f"Please Add Density to {ingredient.name}"
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': 0,
                'available_unit': recipe_unit,
                'status': 'ERROR',
                'error': str(e)
            })
            all_ok = False

    return {
        'stock_check': results,
        'all_ok': all_ok
    }