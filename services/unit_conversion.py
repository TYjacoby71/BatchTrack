
from models import InventoryUnit
from fault_log_utils import log_fault

class UnitConversionService:
    @staticmethod
    def convert(amount, from_unit, to_unit, density=None):
        if from_unit == to_unit:
            return amount

        try:
            f = InventoryUnit.query.filter_by(name=from_unit).first()
            t = InventoryUnit.query.filter_by(name=to_unit).first()
            if not f or not t:
                raise ValueError(f"Unknown units: {from_unit}, {to_unit}")

            if f.type != t.type:
                if {'volume', 'weight'} <= {f.type, t.type} and density:
                    if f.type == 'volume':
                        return (amount * f.base_equivalent * density) / t.base_equivalent
                    else:
                        return (amount * f.base_equivalent / density) / t.base_equivalent
                raise ValueError(f"Cannot convert {f.type} to {t.type} without density")

            return (amount * f.base_equivalent) / t.base_equivalent

        except Exception as e:
            log_fault("UnitConversionService failed", {
                "amount": amount,
                "from": from_unit,
                "to": to_unit,
                "error": str(e)
            })
            return amount  # fallback to raw value
