
from models import Unit, IngredientCategory
from typing import Optional, Tuple

class UnitConversionService:
    @staticmethod
    def convert(amount: float, from_unit: str, to_unit: str, density: Optional[float] = None) -> Tuple[float, str]:
        """Convert between units using the Universal Unit Conversion System (UUCS)"""
        from_unit_obj = Unit.query.filter_by(name=from_unit).first()
        to_unit_obj = Unit.query.filter_by(name=to_unit).first()
        
        if not from_unit_obj or not to_unit_obj:
            raise ValueError("Invalid units")
            
        # Convert to base unit first
        base_amount = amount * from_unit_obj.multiplier_to_base
        
        # Then convert to target unit
        result = base_amount / to_unit_obj.multiplier_to_base
        
        return result, to_unit

