
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
    for type_, units in CONVERSIONS.items():
        if unit in units:
            return type_
    return None

def convert_units(value, from_unit, to_unit):
    unit_type = get_unit_type(from_unit)
    if not unit_type or unit_type != get_unit_type(to_unit):
        return None
        
    # Convert to base unit first, then to target unit
    base_value = value * CONVERSIONS[unit_type][from_unit]
    return base_value / CONVERSIONS[unit_type][to_unit]
