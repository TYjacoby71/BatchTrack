
from models import db, InventoryItem
import logging

logger = logging.getLogger(__name__)

def check_ingredient_stock(recipe, scale):
    results = []
    for ingredient in recipe.recipe_ingredients:
        needed = ingredient.amount * scale
        inventory_item = InventoryItem.query.get(ingredient.inventory_item_id)
        if not inventory_item:
            continue
            
        available = inventory_item.quantity or 0
        if available >= needed:
            status = "OK"
        elif available > 0:
            status = "LOW"
        else:
            status = "NEEDED"
            
        results.append({
            "type": "ingredient",
            "name": inventory_item.name,
            "needed": round(needed, 2),
            "available": round(available, 2),
            "unit": ingredient.unit,
            "status": status
        })
    return results

def check_container_stock(recipe, scale):
    results = []
    if not recipe.requires_containers or not recipe.allowed_containers:
        return results
        
    for container in recipe.allowed_containers:
        needed = scale  # One container per scale unit
        available = container.quantity or 0
        
        if available >= needed:
            status = "OK"
        elif available > 0:
            status = "LOW"
        else:
            status = "NEEDED"
            
        results.append({
            "type": "container",
            "name": container.name,
            "needed": int(needed),
            "available": int(available),
            "storage_unit": container.storage_unit,
            "status": status
        })
    return results
