from models import InventoryItem, Recipe
from services.unit_conversion import ConversionEngine

def check_stock_for_recipe(recipe, scale=1.0):
    errors = []
    plan = []

    for ing in recipe.recipe_ingredients:
        inventory = InventoryItem.query.filter_by(id=ing.inventory_item_id).first()
        if not inventory:
            errors.append(f"Missing inventory item for {ing.inventory_item.name}")
            continue

        required_qty = ing.amount * scale
        required_unit = ing.unit
        stock_qty = inventory.quantity
        stock_unit = inventory.unit
        density = inventory.category.default_density if inventory.category else 1.0

        try:
            converted = ConversionEngine.convert_units(
                stock_qty, stock_unit, required_unit, 
                ingredient_id=inventory.id, 
                density=density
            )
        except Exception as e:
            errors.append(f"Unit mismatch for {inventory.name} ({str(e)})")
            continue

        if converted is None:
            errors.append(f"Conversion failed for {inventory.name}")
            continue

        if round(converted, 4) < round(required_qty, 4):
            errors.append(f"Insufficient {inventory.name}: need {required_qty} {required_unit}, have {converted:.2f}")
            continue

        plan.append({
            "name": inventory.name,
            "required": f"{required_qty} {required_unit}",
            "available": f"{stock_qty} {stock_unit}",
            "status": "ok"
        })

    return {
        "errors": errors,
        "plan": plan,
        "status": "ok" if not errors else "error"
    }