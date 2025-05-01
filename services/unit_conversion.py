
from datetime import datetime
from flask_login import current_user
from models import db, Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog

class ConversionEngine:
    @staticmethod
    def round_value(value, decimals=2):
        return round(value, decimals)

    @staticmethod
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None):
        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()

        if not from_u or not to_u:
            raise ValueError(f"Unknown unit(s): {from_unit}, {to_unit}")

        conversion_type = 'unknown'
        used_density = None
        converted = None

        # 1. Custom Mapping
        mapping = CustomUnitMapping.query.filter_by(from_unit=from_unit, to_unit=to_unit).first()
        if mapping:
            converted = amount * mapping.multiplier
            conversion_type = 'custom'

        # 2. Direct (same unit)
        elif from_unit == to_unit:
            converted = amount
            conversion_type = 'direct'

        # 3. Same-type base conversion (volume → volume, weight → weight)
        elif from_u.type == to_u.type:
            if from_unit == to_unit:
                converted = amount
            else:
                try:
                    base_amount = amount * float(from_u.multiplier_to_base)
                    converted = base_amount / float(to_u.multiplier_to_base)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid conversion between {from_unit} and {to_unit}")
            conversion_type = 'direct'

        # 4. Cross-type: volume ↔ weight
        elif {'volume', 'weight'} <= {from_u.type, to_u.type}:
            # Pull density if not passed
            if density is None and ingredient_id:
                ingredient = Ingredient.query.get(ingredient_id)
                if ingredient:
                    density = ingredient.density or None
                    if density is None and ingredient.category:
                        density = ingredient.category.default_density
            if density is None:
                raise ValueError(f"Missing density for conversion from {from_u.name} to {to_u.name}")
            used_density = density

            if from_u.type == 'volume':
                grams = amount * from_u.multiplier_to_base * density
                converted = grams / to_u.multiplier_to_base
            else:  # weight → volume
                ml = (amount * from_u.multiplier_to_base) / density
                converted = ml / to_u.multiplier_to_base

            conversion_type = 'density'

        else:
            raise ValueError(f"Cannot convert {from_u.type} to {to_u.type} without a custom mapping")

        # Log it
        log = ConversionLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            timestamp=datetime.utcnow(),
            amount=amount,
            from_unit=from_unit,
            to_unit=to_unit,
            result=converted,
            ingredient_id=ingredient_id,
            density_used=used_density
        )
        db.session.add(log)
        db.session.commit()

        # Return structured metadata
        return {
            'converted_value': ConversionEngine.round_value(converted),
            'conversion_type': conversion_type,
            'density_used': used_density,
            'from': from_unit,
            'to': to_unit,
            'requires_attention': conversion_type in ['custom', 'density']
        }
