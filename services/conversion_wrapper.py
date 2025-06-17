
from services.unit_conversion import ConversionEngine

def safe_convert(amount, from_unit, to_unit, ingredient_id=None, density=None):
    try:
        result = ConversionEngine.convert_units(
            amount,
            from_unit,
            to_unit,
            ingredient_id=ingredient_id,
            density=density
        )
        return {"ok": True, "result": result}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
