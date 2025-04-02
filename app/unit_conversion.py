
from unit_converter import UnitConversionService

# Create a singleton instance
converter = UnitConversionService()

def convert_unit(amount, from_unit, to_unit, material="water"):
    return converter.convert(amount, from_unit, to_unit, material)

def can_fulfill(stock_qty, stock_unit, needed_qty, needed_unit):
    try:
        stock_qty = float(stock_qty)
        needed_qty = float(needed_qty)
        converted_needed = converter.convert(needed_qty, needed_unit, stock_unit)
        if converted_needed is None:
            return False
        return stock_qty >= converted_needed
    except:
        return False

def check_stock_availability(needed_qty, needed_unit, stock_qty, stock_unit, material="water"):
    try:
        if not needed_qty or not stock_qty or not needed_unit or not stock_unit:
            return {"status": "LOW", "converted": 0, "unit": needed_unit}

        needed_qty = float(needed_qty)
        stock_qty = float(stock_qty)
        converted_stock = converter.convert(stock_qty, stock_unit, needed_unit, material=material)

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
