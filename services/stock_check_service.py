
from models import Recipe, InventoryItem
from app import db
from services.unit_conversion_service import convert_units

def check_stock(recipe_id, scale, container_plan, flex_mode):
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return {"error": "Recipe not found"}

    results = []
    all_ok = True

    # Ingredients check
    for ingredient in recipe.ingredients:
        scaled_needed = ingredient.amount * scale
        inventory_item = InventoryItem.query.get(ingredient.inventory_item_id)

        if not inventory_item:
            results.append({
                "type": "ingredient",
                "name": ingredient.name,
                "needed": scaled_needed,
                "available": 0,
                "status": "NEEDED"
            })
            all_ok = False
            continue

        needed_in_inventory_unit = convert_units(
            scaled_needed, 
            ingredient.unit, 
            inventory_item.unit
        )

        available = inventory_item.quantity

        if available >= needed_in_inventory_unit:
            status = "OK"
        elif available > 0:
            status = "LOW"
            all_ok = False
        else:
            status = "NEEDED"
            all_ok = False

        results.append({
            "type": "ingredient",
            "name": ingredient.name,
            "needed": needed_in_inventory_unit,
            "available": available,
            "status": status
        })

    # Containers check
    if not recipe.requires_containers:
        return {"stock_check": results, "all_ok": all_ok}
        
    for container_selection in container_plan:
        try:
            container_id = int(container_selection['id'])
            container_quantity_needed = int(container_selection['quantity'])
        except (ValueError, KeyError, TypeError):
            results.append({
                "type": "container",
                "name": "Invalid container data",
                "needed": 0,
                "available": 0,
                "status": "NEEDED"
            })
            all_ok = False
            continue

        inventory_container = InventoryItem.query.get(container_id)

        if not inventory_container:
            results.append({
                "type": "container",
                "name": f"Container ID {container_id}",
                "needed": container_quantity_needed,
                "available": 0,
                "status": "NEEDED"
            })
            all_ok = False
            continue

        available = inventory_container.quantity

        if available >= container_quantity_needed:
            status = "OK"
        elif available > 0:
            status = "LOW"
            all_ok = False
        else:
            status = "NEEDED"
            all_ok = False

        results.append({
            "type": "container",
            "name": inventory_container.name,
            "needed": container_quantity_needed,
            "available": available,
            "status": status
        })

    return {
        "stock_check": results,
        "all_ok": all_ok
    }
