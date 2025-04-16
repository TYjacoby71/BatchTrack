
from models import Ingredient, RecipeIngredient
from services.unit_conversion import UnitConversionService
from fault_log_utils import log_fault

def check_stock_for_recipe(recipe, scale=1.0):
    try:
        results = []
        all_ok = True

        if not recipe or not recipe.recipe_ingredients:
            return [], True

        for assoc in recipe.recipe_ingredients:
            if not assoc or not assoc.ingredient:
                continue
                
            ing = assoc.ingredient
            needed = assoc.amount * scale
            
            try:
                needed_converted = UnitConversionService.convert(needed, assoc.unit, ing.unit)
            except Exception as e:
                log_fault(f"Unit conversion error for {ing.name}", {"error": str(e)})
                needed_converted = needed

            available = ing.quantity if ing.quantity is not None else 0
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
    except Exception as e:
        log_fault("Stock check error", {"error": str(e), "recipe_id": recipe.id if recipe else None})
        return [], False
