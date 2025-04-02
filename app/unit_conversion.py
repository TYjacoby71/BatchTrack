conversion_factors = {
    ('gallon', 'cup'): 16,
    ('cup', 'gallon'): 1 / 16,
    ('liter', 'ml'): 1000,
    ('ml', 'liter'): 1 / 1000,
    ('oz', 'ml'): 29.5735,
    ('ml', 'oz'): 1 / 29.5735
}

def convert_unit(amount, from_unit, to_unit):
    if from_unit == to_unit:
        return amount
    key = (from_unit.lower(), to_unit.lower())
    if key in conversion_factors:
        return amount * conversion_factors[key]
    return None

def check_stock_availability(needed_qty, needed_unit, stock_qty, stock_unit):
    converted_stock = convert_unit(stock_qty, stock_unit, needed_unit)
    if converted_stock is None:
        return {"status": "conversion_error", "converted": None}
    status = "OK" if converted_stock >= needed_qty else "ORDER NEEDED" if converted_stock < 0.1 else "LOW"
    return {
        "status": status,
        "converted": round(converted_stock, 2),
        "unit": needed_unit
    }