
from models import InventoryItem, Recipe
from services.unit_conversion import ConversionEngine

def check_stock_for_recipe(recipe, scale=1.0):
    report = []
    all_ok = True

    for ingredient in recipe.recipe_ingredients:
        inventory_item = InventoryItem.query.get(ingredient.inventory_item_id)
        if not inventory_item:
            report.append({
                "ingredient": ingredient.name,
                "recipe_unit": ingredient.unit,
                "original_amount": ingredient.amount,
                "available": 0,
                "unit": ingredient.unit,
                "status": "NEEDED"
            })
            all_ok = False
            continue

        needed_amount = ingredient.amount * scale
        
        # Convert inventory amount to recipe unit
        converted_amount = ConversionEngine.convert_units(
            inventory_item.quantity,
            inventory_item.unit,
            ingredient.unit,
            ingredient_id=inventory_item.id
        )

        if converted_amount is None:
            report.append({
                "ingredient": ingredient.name,
                "recipe_unit": ingredient.unit,
                "original_amount": ingredient.amount,
                "available": inventory_item.quantity,
                "unit": inventory_item.unit,
                "status": "UNIT_MISMATCH"
            })
            all_ok = False
            continue

        if converted_amount >= needed_amount:
            status = "OK"
        elif converted_amount > 0:
            status = "LOW"
            all_ok = False
        else:
            status = "NEEDED"
            all_ok = False

        report.append({
            "ingredient": ingredient.name,
            "recipe_unit": ingredient.unit,
            "original_amount": ingredient.amount,
            "available": converted_amount,
            "unit": ingredient.unit,
            "status": status
        })

    return report, all_ok
