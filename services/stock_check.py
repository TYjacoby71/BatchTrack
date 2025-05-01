
from models import db, Recipe, InventoryItem
from services.unit_conversion import ConversionEngine

def universal_stock_check(recipe, scale=1.0, container_plan=None):
    """Universal Stock Check Service (USCS)"""
    results = []
    all_ok = True
    
    # Check ingredients with UUCS integration
    for recipe_ingredient in recipe.recipe_ingredients:
        ingredient = recipe_ingredient.inventory_item
        needed_amount = recipe_ingredient.amount * scale
        
        # Get stock level and convert units using UUCS
        available = ingredient.quantity or 0
        stock_unit = ingredient.unit
        recipe_unit = recipe_ingredient.unit
        density = ingredient.category.default_density if ingredient.category else 1.0

        try:
            available_converted = ConversionEngine.convert_units(
                available, 
                stock_unit, 
                recipe_unit,
                ingredient_id=ingredient.id,
                density=density
            )
            
            if available_converted >= needed_amount:
                status = 'OK'
            elif available_converted >= needed_amount * 0.5:
                status = 'LOW'
                all_ok = False
            else:
                status = 'NEEDED'
                all_ok = False
                
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
        except Exception as e:
            results.append({
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': 0,
                'status': 'ERROR',
                'error': str(e)
            })
            all_ok = False

    # Check containers if recipe requires them
    if recipe.requires_containers:
        projected_yield = recipe.predicted_yield * scale
        
        for container in recipe.allowed_containers:
            if not container:
                continue
                
            available = container.quantity or 0
            if available > 0:
                status = 'OK'
            else:
                status = 'NEEDED'
                all_ok = False
                
            results.append({
                'type': 'container',
                'name': container.name,
                'needed': 1,
                'available': available,
                'unit': 'count',
                'status': status
            })

    return {
        'stock_check': results,
        'all_ok': all_ok
    }
