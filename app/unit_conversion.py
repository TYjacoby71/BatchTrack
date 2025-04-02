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

def can_fulfill(stock_qty, stock_unit, needed_qty, needed_unit):
    try:
        converted = convert_unit(needed_qty, needed_unit, stock_unit)
        if converted is None:
            return False
        return stock_qty >= converted
    except:
        return False

def check_stock_availability(needed_qty, needed_unit, stock_qty, stock_unit):
    try:
        if not needed_qty or not stock_qty or not needed_unit or not stock_unit:
            return {"status": "LOW", "converted": 0, "unit": needed_unit}
        
        needed_qty = float(needed_qty)
        stock_qty = float(stock_qty)
        converted_stock = convert_unit(stock_qty, stock_unit, needed_unit)
        
        if converted_stock is None:
            return {"status": "conversion_error", "converted": 0, "unit": needed_unit}
            
        status = "OK" if converted_stock >= needed_qty else "ORDER NEEDED" if converted_stock < 0.1 else "LOW"
        return {
            "status": status,
            "converted": round(converted_stock, 2),
            "unit": needed_unit
        }
    except (ValueError, TypeError):
        return {"status": "conversion_error", "converted": 0, "unit": needed_unit}