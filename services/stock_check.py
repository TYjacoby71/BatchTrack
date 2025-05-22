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
            # Let UUCS handle all conversion logic and errors
            conversion_result = ConversionEngine.convert_units(
                available,
                stock_unit,
                recipe_unit,
                ingredient_id=ingredient.id
            )
            available_converted = conversion_result['converted_value']

            # Only handle inventory level checks here
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
            status = 'ERROR'
            if "density" in str(e).lower():
                status = 'DENSITY_MISSING'
            
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': 0,  # Keep as number for template formatting
                'available_unit': recipe_unit,
                'status': status,
                'error_msg': str(e)
            })
            all_ok = False

    return {
        'stock_check': results,
        'all_ok': all_ok
    }