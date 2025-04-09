
from models import Ingredient
from unit_conversion_utils import convert_units

def check_stock_for_recipe(recipe, scale=1.0):
    results = []
    all_ok = True

    if not hasattr(recipe, 'ingredients') or not recipe.ingredients:
        return [], True

    for ing in recipe.ingredients:
        name = ing['name']
        required_amt = ing['amount'] * scale
        from_unit = ing.get('unit', 'ml')  # fallback

        stock_item = Ingredient.query.filter_by(name=name).first()
        to_unit = stock_item.unit if stock_item else from_unit
        available = stock_item.quantity if stock_item else 0

        try:
            needed_converted = convert_units(required_amt, from_unit, to_unit)
        except:
            needed_converted = required_amt
            to_unit = from_unit

        if available >= needed_converted:
            status = 'OK'
        elif available > 0:
            status = 'LOW'
            all_ok = False
        else:
            status = 'NEEDED'
            all_ok = False

        results.append({
            'name': name,
            'unit': to_unit,
            'needed': needed_converted,
            'available': available,
            'status': status
        })

    return results, all_ok
