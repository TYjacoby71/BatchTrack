
volume_units = {
    "ml": 1,
    "milliliter": 1,
    "l": 1000,
    "liter": 1000,
    "tsp": 4.92892,
    "tbsp": 14.7868,
    "fl oz": 29.5735,
    "cup": 236.588,
    "pint": 473.176,
    "quart": 946.353,
    "gallon": 3785.41
}

weight_units = {
    "mg": 0.001,
    "g": 1,
    "gram": 1,
    "kg": 1000,
    "oz": 28.3495,
    "lb": 453.592
}

def convert_unit(amount, from_unit, to_unit):
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    if from_unit in volume_units and to_unit in volume_units:
        base = volume_units
    elif from_unit in weight_units and to_unit in weight_units:
        base = weight_units
    else:
        raise ValueError(f"Incompatible units: {from_unit} → {to_unit}")

    amount_in_base = amount * base[from_unit]
    converted = amount_in_base / base[to_unit]
    return converted

def can_fulfill(stock_qty, stock_unit, required_qty, required_unit):
    try:
        converted_required = convert_unit(required_qty, required_unit, stock_unit)
        return stock_qty >= converted_required, converted_required
    except Exception:
        return False, None
