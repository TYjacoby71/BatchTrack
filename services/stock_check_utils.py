from models import InventoryItem, Recipe
from services.unit_conversion import ConversionEngine


def convert_units(amount, from_unit, to_unit, density=1.0):
    """Converts units of measurement using UUCS."""
    try:
        from services.unit_conversion_service import convert_units as ucs_convert_units
        return ucs_convert_units(amount, from_unit, to_unit, density=density)
    except Exception as e:
        print(f"UUCS Conversion error: {e}")
        return None



def get_available_containers(recipe_yield, recipe_unit, scale=1.0):
    projected_volume = recipe_yield * scale

    # Step 1: Find in-stock containers
    in_stock = []
    inventory = InventoryItem.query.filter_by(type='container').all()

    for item in inventory:
        container = Container.query.get(item.container_id)
        if not container or item.quantity <= 0:
            continue

        converted_capacity = convert_units(container.storage_amount, container.storage_unit, recipe_unit)
        if converted_capacity is None:
            continue

        in_stock.append({
            "id": container.id,
            "name": container.name,
            "storage_amount": converted_capacity,
            "storage_unit": recipe_unit,
            "stock_qty": item.quantity
        })

    # Step 2: Sort containers from largest to smallest
    sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)

    # Step 3: Greedy fill logic
    plan = []
    remaining = projected_volume

    for c in sorted_containers:
        per_unit = c['storage_amount']
        if per_unit <= 0:
            continue

        while remaining >= per_unit and c['stock_qty'] > 0:
            plan.append({
                "id": c['id'],
                "name": c['name'],
                "capacity": per_unit,
                "unit": recipe_unit,
                "quantity": 1
            })
            remaining -= per_unit
            c['stock_qty'] -= 1

    return {
        "available": sorted_containers,
        "plan": plan
    }