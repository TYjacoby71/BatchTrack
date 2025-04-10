
from models import InventoryUnit

class UnitConversionService:
    @staticmethod
    def convert(amount, from_unit, to_unit):
        if from_unit == to_unit:
            return amount
            
        from_unit_obj = InventoryUnit.query.filter_by(name=from_unit).first()
        to_unit_obj = InventoryUnit.query.filter_by(name=to_unit).first()
        
        if not from_unit_obj or not to_unit_obj:
            return amount
            
        if from_unit_obj.base_equivalent and to_unit_obj.base_equivalent:
            return amount * (from_unit_obj.base_equivalent / to_unit_obj.base_equivalent)
            
        return amount
