
from models import InventoryItem, RecipeIngredient
from services.unit_conversion import ConversionEngine

def get_available_containers():
    """Get all available containers ordered by name"""
    return InventoryItem.query.filter_by(type='container').order_by(InventoryItem.name).all()

def check_stock_for_recipe(recipe, scale=1.0, container_ids=None):
    """
    Comprehensive stock check that includes both ingredients and containers
    """
    results = []
    all_ok = True

    # Check ingredients
    for assoc in recipe.recipe_ingredients:
        ing = assoc.inventory_item
        if not ing:
            continue
        needed = assoc.amount * scale
        try:
            needed_converted = ConversionEngine.convert_units(needed, assoc.unit, ing.unit)
        except Exception as e:
            print(f"Conversion error for {ing.name}: {str(e)}")
            needed_converted = needed
            status = 'ERROR'
            all_ok = False

        available = ing.quantity
        status = 'OK' if available >= needed_converted else 'LOW' if available > 0 else 'NEEDED'
        if status != 'OK':
            all_ok = False
            
        results.append({
            'name': ing.name,
            'ingredient': ing,
            'recipe_unit': recipe_ingredient.unit,
            'unit': ing.unit,
            'needed': round(needed_converted, 2),
            'available': round(available, 2),
            'status': status,
            'type': 'ingredient'
        })

    # Check containers if specified
    if container_ids:
        container_results, containers_ok = check_container_availability(container_ids, scale)
        results.extend(container_results)
        all_ok = all_ok and containers_ok

    return results, all_ok

def check_container_availability(containers, scale=1.0):
    results = []
    all_ok = True
    
    from models import InventoryItem

    for container in containers:
        container_item = InventoryItem.query.get(container['id'])
        if not container_item or container_item.type != 'container':
            continue

        needed = container['quantity']
        available = container_item.quantity

        if available >= needed:
            status = 'OK'
        elif available > 0:
            status = 'LOW'
            all_ok = False
        else:
            status = 'NEEDED'
            all_ok = False

        results.append({
            'name': container_item.name,
            'needed': needed,
            'available': available,
            'status': status,
            'type': 'container'
        })

    return results, all_ok
