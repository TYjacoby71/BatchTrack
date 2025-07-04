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

                # 1. Custom Mapping (including compound)
                def find_conversion_path(start, end, visited=None):
                    if visited is None:
                        visited = set()
                    if start == end:
                        return []
                    if start in visited:
                        return None
                    visited.add(start)
                    mappings = CustomUnitMapping.query.filter_by(from_unit=start).all()
                    for mapping in mappings:
                        path = find_conversion_path(mapping.to_unit, end, visited.copy())
                        if path is not None:
                            return [mapping] + path
                    return None

                conversion_path = find_conversion_path(from_unit, to_unit)
                if conversion_path:
                    converted = amount
                    for mapping in conversion_path:
                        converted *= mapping.multiplier
                    conversion_type = 'custom_compound' if len(conversion_path) > 1 else 'custom'

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
                            from_multiplier = float(from_u.conversion_factor) if from_u.conversion_factor else 1.0
                            to_multiplier = float(to_u.conversion_factor) if to_u.conversion_factor else 1.0
                            base_amount = amount * from_multiplier
                            converted = base_amount / to_multiplier
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            raise ValueError(f"Invalid conversion between {from_unit} and {to_unit}: {str(e)}")
                    conversion_type = 'direct'

                # 4. Cross-type: volume ↔ weight
                elif {'volume', 'weight'} <= {from_u.type, to_u.type}:
                    # Only use ingredient-level density
                    if density is None and ingredient_id:
                        ingredient = Ingredient.query.get(ingredient_id)
                        if ingredient and ingredient.density:
                            density = ingredient.density
                    if density is None:
                        raise ValueError(f"Missing density for conversion from {from_u.name} to {to_u.name}")
                    used_density = density

                    if from_u.type == 'volume':
                        grams = amount * from_u.conversion_factor * density
                        converted = grams / to_u.conversion_factor
                    else:  # weight → volume
                        ml = (amount * from_u.conversion_factor) / density
                        converted = ml / to_u.conversion_factor

                    conversion_type = 'density'

                else:
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