
from models import db, Recipe, InventoryItem
from services.unit_conversion_service import convert_units

def universal_stock_check(recipe, scale=1.0):
    """Universal Stock Check Service"""
    results = []
    
    # Check ingredients
    for recipe_ingredient in recipe.recipe_ingredients:
        ingredient = recipe_ingredient.inventory_item
        needed_amount = recipe_ingredient.amount * scale
        
        # Get current stock level
        available = ingredient.quantity or 0
        
        # Determine status
        if available >= needed_amount:
            status = 'OK'
        elif available >= needed_amount * 0.5:
            status = 'LOW'
        else:
            status = 'NEEDED'
            
        results.append({
            'type': 'ingredient',
            'name': ingredient.name,
            'needed': needed_amount,
            'available': available,
            'unit': recipe_ingredient.unit,
            'status': status
        })

    # Check containers if recipe requires them
    if recipe.requires_containers and recipe.allowed_containers:
        projected_yield = recipe.predicted_yield * scale
        
        for container in recipe.allowed_containers:
            status = 'OK' if container.quantity > 0 else 'NEEDED'
            results.append({
                'type': 'container',
                'name': container.name,
                'needed': 1,
                'available': container.quantity or 0,
                'unit': 'count',
                'status': status
            })

    return results
