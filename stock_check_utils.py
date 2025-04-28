from models import InventoryItem, RecipeIngredient, Recipe
from services.unit_conversion import ConversionEngine

def get_available_containers():
    """Get all available containers ordered by name"""
    return InventoryItem.query.filter_by(type='container').order_by(InventoryItem.name).all()

def check_stock_for_recipe(recipe, scale=1.0, container_ids=None):
    """Legacy function maintained for compatibility"""
    results = []
    all_ok = True
    
    if not recipe:
        return results, all_ok
        
    for assoc in recipe.recipe_ingredients:
        ing = assoc.inventory_item
        if not ing:
            continue
            
        needed_qty = assoc.amount * scale
        available_qty = ing.quantity
        
        status = 'OK' if available_qty >= needed_qty else ('LOW' if available_qty > 0 else 'NEEDED')
        if status != 'OK':
            all_ok = False
            
        results.append({
            'type': 'ingredient',
            'name': ing.name,
            'needed': round(needed_qty, 2),
            'available': round(available_qty, 2),
            'unit': ing.unit,
            'status': status
        })
    
    return results, all_ok

def check_stock(recipe_id, scale=1.0, containers=[]):
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    results = []

    # Check ingredients
    for assoc in recipe.recipe_ingredients:
        ing = assoc.inventory_item
        if not ing:
            continue

        needed_qty = assoc.amount * scale
        available_qty = ing.quantity

        results.append({
            'type': 'ingredient',
            'name': ing.name,
            'needed': round(needed_qty, 2),
            'available': round(available_qty, 2),
            'unit': ing.unit,
            'status': 'OK' if available_qty >= needed_qty else ('LOW' if available_qty > 0 else 'NEEDED')
        })

    # Check containers
    if containers:
        for c in containers:
            container = InventoryItem.query.get(c.get('id'))
            if not container:
                continue
            needed_qty = int(c.get('quantity', 1))
            available_qty = container.quantity

            results.append({
                'type': 'container',
                'name': container.name,
                'needed': needed_qty,
                'available': available_qty,
                'unit': container.unit,
                'status': 'OK' if available_qty >= needed_qty else ('LOW' if available_qty > 0 else 'NEEDED')
            })

    return results