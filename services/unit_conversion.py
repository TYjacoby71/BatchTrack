
from datetime import datetime
from flask_login import current_user
from models import db, Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog

class ConversionEngine:
    @staticmethod
    def round_value(value, decimals=2):
        return round(value, decimals)

    @staticmethod
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None):
        try:
            from_u = Unit.query.filter_by(name=from_unit).first()
            to_u = Unit.query.filter_by(name=to_unit).first()
            
            if not from_u or not to_u:
                return None

            # First try direct conversion if units are the same
            if from_unit == to_unit:
                return amount

            # Then try same-type conversion through base units
            if from_u.type == to_u.type:
                base_amount = amount * from_u.multiplier_to_base
                result = base_amount / to_u.multiplier_to_base
                return ConversionEngine.round_value(result)

            # Try custom mapping
            custom_mapping = CustomUnitMapping.query.filter_by(from_unit=from_unit, to_unit=to_unit).first()
            if custom_mapping:
                return ConversionEngine.round_value(amount * custom_mapping.multiplier)

            # Handle volume-weight conversions
            if {'volume', 'weight'} <= {from_u.type, to_u.type}:
                if density is None and ingredient_id:
                    ingredient = Ingredient.query.get(ingredient_id)
                    if ingredient:
                        density = ingredient.density
                        if density is None and ingredient.category:
                            density = ingredient.category.default_density
                density = density or 1.0

                if from_u.type == 'volume':
                    grams = amount * from_u.multiplier_to_base * density
                    result = grams / to_u.multiplier_to_base
                else:
                    ml = (amount * from_u.multiplier_to_base) / density
                    result = ml / to_u.multiplier_to_base
                
                result = ConversionEngine.round_value(result)

                # Log the conversion
                log = ConversionLog(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    timestamp=datetime.utcnow(),
                    amount=amount,
                    from_unit=from_unit,
                    to_unit=to_unit,
                    result=result,
                    ingredient_id=ingredient_id,
                    density_used=density
                )
                db.session.add(log)
                db.session.commit()

                return result

            return None
            
        except Exception as e:
            print(f"Conversion error: {str(e)}")
            return None
