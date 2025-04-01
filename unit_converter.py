# Unit conversion system
VOLUME_UNITS = {
    'ml': 1,
    'milliliter': 1,
    'l': 1000,
    'liter': 1000,
    'tsp': 4.92892,
    'tbsp': 14.7868,
    'fl oz': 29.5735,
    'cup': 236.588,
    'pint': 473.176,
    'quart': 946.353,
    'gallon': 3785.41,
    'gal': 3785.41
}

WEIGHT_UNITS = {
    'mg': 0.001,
    'g': 1,
    'gram': 1,
    'kg': 1000,
    'oz': 28.3495,
    'lb': 453.592,
    'pound': 453.592
}

def convert_units(amount, from_unit, to_unit):
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    if from_unit in VOLUME_UNITS and to_unit in VOLUME_UNITS:
        base = VOLUME_UNITS
    elif from_unit in WEIGHT_UNITS and to_unit in WEIGHT_UNITS:
        base = WEIGHT_UNITS
    else:
        return None

    try:
        amount = float(amount)
        base_amount = amount * base[from_unit]
        converted = base_amount / base[to_unit]
        return round(converted, 4)
    except:
        return None

def can_fulfill(stock_qty, stock_unit, needed_qty, needed_unit):
    try:
        stock_qty = float(stock_qty)
        needed_qty = float(needed_qty)
        converted_needed = convert_units(needed_qty, needed_unit, stock_unit)
        if converted_needed is None:
            return False
        return stock_qty >= converted_needed
    except:
        return False

def format_unit_value(value, unit):
    """Format a value with its unit for display"""
    if value is None:
        return "N/A"
    return f"{value:.2f} {unit}"

def check_stock_availability(recipe_qty, recipe_unit, stock_qty, stock_unit):
    """
    Check if there's enough stock for a recipe
    Returns: (bool available, float converted_stock_qty, float needed_qty)
    """
    if not recipe_qty or not stock_qty:
        return False, 0, 0

    converted_stock = convert_units(stock_qty, stock_unit, recipe_unit)
    if converted_stock is None:
        return False, 0, float(recipe_qty)

    return converted_stock >= float(recipe_qty), converted_stock, float(recipe_qty)