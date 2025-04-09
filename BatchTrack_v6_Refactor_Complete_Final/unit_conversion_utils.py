
from models import InventoryUnit

def convert_units(amount, from_unit, to_unit, density=None):
    if from_unit == to_unit:
        return amount  # No conversion needed

    from_u = InventoryUnit.query.filter_by(name=from_unit).first()
    to_u = InventoryUnit.query.filter_by(name=to_unit).first()

    if not from_u or not to_u:
        raise ValueError(f"Unknown unit(s): {from_unit}, {to_unit}")

    # Must be same type or volume↔weight w/ density
    if from_u.type != to_u.type:
        if {'volume', 'weight'} <= {from_u.type, to_u.type} and density:
            if from_u.type == 'volume':
                # volume → weight: ml * g/ml = g
                amount_in_base = amount * from_u.base_equivalent
                grams = amount_in_base * density
                return grams / to_u.base_equivalent
            else:
                # weight → volume: g / (g/ml) = ml
                amount_in_base = amount * from_u.base_equivalent
                ml = amount_in_base / density
                return ml / to_u.base_equivalent
        else:
            raise ValueError(f"Cannot convert {from_u.type} to {to_u.type} without density")

    # Same type: convert through base unit
    base_amount = amount * from_u.base_equivalent
    return base_amount / to_u.base_equivalent
