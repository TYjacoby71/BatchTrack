from datetime import datetime
from flask_login import current_user
from ..models import db, Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog

class ConversionEngine:
    @staticmethod
    def round_value(value, decimals=3):
        return round(value, decimals)

    @staticmethod
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None):
        # Validate input parameters
        if not isinstance(amount, (int, float)) or amount < 0:
            raise ValueError(f"Invalid amount: {amount}. Must be a positive number.")
        if not from_unit or not isinstance(from_unit, str):
            raise ValueError(f"Invalid from_unit: {from_unit}")
        if not to_unit or not isinstance(to_unit, str):
            raise ValueError(f"Invalid to_unit: {to_unit}")

        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()

        if not from_u:
            raise ValueError(f"Unknown source unit: {from_unit}")
        if not to_u:
            raise ValueError(f"Unknown target unit: {to_unit}")

        conversion_type = 'unknown'
        used_density = None
        converted = None

        # 1. Custom Mapping - check if either unit has a custom mapping
        custom_from = CustomUnitMapping.query.filter_by(unit_name=from_unit).first()
        custom_to = CustomUnitMapping.query.filter_by(unit_name=to_unit).first()
        
        # If we have custom mappings, convert through base units
        if custom_from or custom_to:
            try:
                # Convert from_unit to its base
                if custom_from:
                    base_amount = amount * custom_from.conversion_factor
                    base_unit = custom_from.base_unit
                else:
                    base_amount = amount * from_u.conversion_factor
                    base_unit = from_u.base_unit
                
                # Convert from base to to_unit
                if custom_to:
                    converted = base_amount / custom_to.conversion_factor
                else:
                    converted = base_amount / to_u.conversion_factor
                    
                conversion_type = 'custom'
            except (AttributeError, TypeError, ZeroDivisionError):
                # Fall through to other conversion methods
                pass

        # 2. Direct (same unit) 
        if converted is None and from_unit == to_unit:
            converted = amount
            conversion_type = 'direct'

        # 3. Same-type base conversion (volume → volume, weight → weight)
        elif converted is None and from_u.type == to_u.type:
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
        elif converted is None and {'volume', 'weight'} <= {from_u.type, to_u.type}:
            # Only use ingredient-level density
            if density is None and ingredient_id:
                ingredient = Ingredient.query.get(ingredient_id)
                if ingredient and ingredient.density:
                    density = ingredient.density
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

        elif converted is None:
            raise ValueError(f"Cannot convert {from_u.type} to {to_u.type} without a custom mapping")

        # Log it only if user is authenticated and has organization
        if current_user and current_user.is_authenticated and current_user.organization_id:
            log = ConversionLog(
                user_id=current_user.id,
                amount=amount,
                from_unit=from_unit,
                to_unit=to_unit,
                result=converted,
                conversion_type='unit_to_unit',
                organization_id=current_user.organization_id
            )
            db.session.add(log)
            try:
                db.session.commit()
            except Exception as e:
                print(f"Error logging conversion: {e}")
                db.session.rollback()

        # Return structured metadata
        return {
            'converted_value': ConversionEngine.round_value(converted),
            'conversion_type': conversion_type,
            'density_used': used_density,
            'from': from_unit,
            'to': to_unit,
            'requires_attention': conversion_type in ['custom', 'density']
        }