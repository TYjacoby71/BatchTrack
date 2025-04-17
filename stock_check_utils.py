
from models import InventoryItem, RecipeIngredient
from services.unit_conversion import UnitConversionService

def check_stock_for_recipe(recipe, scale=1.0):
    results = []
    all_ok = True

    for assoc in recipe.recipe_ingredients:
        ing = assoc.ingredient
        if not ing:
            continue
        needed = assoc.amount * scale
        try:
            needed_converted = UnitConversionService.convert(needed, assoc.unit, ing.unit)
        except:
            needed_converted = needed

        available = ing.quantity
        status = 'OK' if available >= needed_converted else 'LOW' if available > 0 else 'NEEDED'
        if status != 'OK':
            all_ok = False

        results.append({
            'name': ing.name,
            'unit': ing.unit,
            'needed': round(needed_converted, 2),
            'available': round(available, 2),
            'status': status
        })

    return results, all_ok
