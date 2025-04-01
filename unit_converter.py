
# Conversion rates to base units (mL for volume, g for weight)
CONVERSIONS = {
    'volume': {
        'mL': 1,
        'cL': 10,
        'L': 1000,
        'fl oz': 29.5735,
        'tsp': 4.92892,
        'tbsp': 14.7868,
        'cup': 236.588,
        'pint': 473.176,
        'quart': 946.353,
        'gallon': 3785.41,
        'gal': 3785.41,  # Adding common abbreviation
        'dash': 0.92,
        'drop': 0.05
    },
    'weight': {
        'mg': 0.001,
        'g': 1,
        'kg': 1000,
        'oz': 28.3495,
        'lb': 453.592
    },
    'count': {
        'unit': 1,
        'piece': 1,
        'each': 1
    }
}

def get_unit_type(unit):
    """Get the measurement type for a given unit"""
    for type_, units in CONVERSIONS.items():
        if unit in units:
            return type_
    return None

def convert_units(value, from_unit, to_unit):
    """Convert a value from one unit to another"""
    if not value:
        return None
        
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
        
    unit_type = get_unit_type(from_unit)
    if not unit_type or unit_type != get_unit_type(to_unit):
        return None
        
    # Convert to base unit first, then to target unit
    base_value = value * CONVERSIONS[unit_type][from_unit]
    return base_value / CONVERSIONS[unit_type][to_unit]

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

def format_unit_value(value, unit):
    """Format a value with its unit for display"""
    if value is None:
        return "N/A"
    return f"{value:.2f} {unit}"
