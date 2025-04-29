
from models import Recipe, InventoryItem, Container
from app.utils import convert_units
from typing import Dict, List, Optional

def check_stock(recipe_id: int, scale: float, container_plan: List[Dict]) -> Dict:
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return {"error": "Recipe not found"}

    results = []
    all_ok = True

    # Check ingredients
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

        if inventory_item.quantity >= scaled_needed:
            status = "OK"
        elif inventory_item.quantity > 0:
            status = "LOW"
            all_ok = False
        else:
            status = "NEEDED" 
            all_ok = False

        results.append({
            "type": "ingredient",
            "name": inventory_item.name,
            "needed": scaled_needed,
            "available": inventory_item.quantity,
            "unit": inventory_item.unit,
            "status": status
        })

    # Check containers if required
    if recipe.requires_containers:
        for container in container_plan:
            container_id = container.get('id')
            quantity_needed = container.get('quantity', 0)
            
            inventory_container = InventoryItem.query.get(container_id)
            if not inventory_container:
                results.append({
                    "type": "container",
                    "name": f"Container ID {container_id}",
                    "needed": quantity_needed,
                    "available": 0,
                    "status": "NEEDED"
                })
                all_ok = False
                continue

            if inventory_container.quantity >= quantity_needed:
                status = "OK"
            elif inventory_container.quantity > 0:
                status = "LOW"
                all_ok = False
            else:
                status = "NEEDED"
                all_ok = False

            results.append({
                "type": "container",
                "name": inventory_container.name,
                "needed": quantity_needed,
                "available": inventory_container.quantity,
                "unit": inventory_container.unit,
                "status": status
            })

    return {
        "stock_check": results,
        "all_ok": all_ok
    }

def get_available_containers(recipe_yield: float, recipe_unit: str, scale: float = 1.0) -> Dict:
    projected_volume = recipe_yield * scale
    in_stock = []
    
    for item in InventoryItem.query.filter_by(type='container').all():
        if item.quantity <= 0:
            continue
            
        container = Container.query.get(item.container_id)
        if not container:
            continue

        converted_capacity = convert_units(container.storage_amount, 
                                        container.storage_unit, 
                                        recipe_unit)
        if converted_capacity is None:
            continue

        in_stock.append({
            "id": container.id,
            "name": container.name,
            "storage_amount": converted_capacity,
            "storage_unit": recipe_unit,
            "stock_qty": item.quantity
        })

    sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)
    plan = []
    remaining = projected_volume

    for container in sorted_containers:
        while remaining >= container['storage_amount'] and container['stock_qty'] > 0:
            plan.append({
                "id": container['id'],
                "name": container['name'],
                "capacity": container['storage_amount'],
                "unit": recipe_unit,
                "quantity": 1
            })
            remaining -= container['storage_amount']
            container['stock_qty'] -= 1

    return {
        "available": sorted_containers,
        "plan": plan
    }
