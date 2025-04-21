
from datetime import datetime
from flask_login import current_user
from models import db, Unit, CustomUnitMapping, ConversionLog, InventoryItem

class UnitConversionService:
    @staticmethod
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None):
        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()
        if not from_u or not to_u:
            raise ValueError(f"Unknown unit(s): {from_unit}, {to_unit}")

        custom_mapping = CustomUnitMapping.query.filter_by(from_unit=from_unit, to_unit=to_unit).first()
        if custom_mapping:
            result = amount * custom_mapping.multiplier
        elif from_unit == to_unit:
            result = amount
        elif from_u.type == to_u.type:
            base_amount = amount * from_u.multiplier_to_base
            result = base_amount / to_u.multiplier_to_base
        elif {'volume', 'weight'} <= {from_u.type, to_u.type}:
            if density is None and ingredient_id:
                ingredient = InventoryItem.query.get(ingredient_id)
                if ingredient and ingredient.category:
                    density = ingredient.category.default_density
                density = density or 1.0
            if density is None:
                density = 1.0
            if from_u.type == 'volume':
                grams = amount * from_u.multiplier_to_base * density
                result = grams / to_u.multiplier_to_base
            else:
                ml = (amount * from_u.multiplier_to_base) / density
                result = ml / to_u.multiplier_to_base
        else:
            raise ValueError(f"Cannot convert {from_u.type} to {to_u.type} without a custom mapping")

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

        return round(result, 2)
