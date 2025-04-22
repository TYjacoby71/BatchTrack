
from models import InventoryItem, RecipeIngredient
from services.unit_conversion import ConversionEngine

def check_stock_for_recipe(recipe, scale=1.0):
    results = []
    all_ok = True

    for assoc in recipe.recipe_ingredients:
        ing = assoc.inventory_item
        if not ing:
            continue
        needed = assoc.amount * scale
        try:
            needed_converted = ConversionEngine.convert_units(needed, assoc.unit, ing.unit)
        except Exception as e:
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

def check_container_availability(container_ids, scale=1.0):
    results = []
    all_ok = True
    
    from models import InventoryItem

    for cid in container_ids:
        container = InventoryItem.query.get(cid)
        if not container or container.type != 'container':
            continue

        required = 1 * scale  # assume 1 per unit for now
        available = container.quantity
        unit = container.unit

        if available >= required:
            status = 'OK'
        elif available > 0:
            status = 'LOW'
            all_ok = False
        else:
            status = 'NEEDED'
            all_ok = False

        results.append({
            'name': container.name,
            'unit': unit,
            'needed': required,
            'available': available,
            'status': status,
            'type': 'container'
        })

    return results, all_ok
