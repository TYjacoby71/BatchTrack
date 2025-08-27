
from datetime import datetime
from flask_login import current_user
from ...models import db, Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog

class ConversionEngine:
    @staticmethod
    def round_value(value, decimals=3):
        """Round value with protection against floating point precision issues"""
        if value is None:
            return None
        # Use decimal for more precise rounding
        from decimal import Decimal, ROUND_HALF_UP
        decimal_value = Decimal(str(value))
        rounded_decimal = decimal_value.quantize(Decimal('0.' + '0' * decimals), rounding=ROUND_HALF_UP)
        return float(rounded_decimal)

    @staticmethod
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None):
        """
        Convert units with structured error handling for wall of drawers protocol

        Returns:
        {
            'success': bool,
            'converted_value': float | None,
            'error_code': str | None,
            'error_data': dict | None,
            'conversion_type': str,
            'density_used': float | None,
            'from': str,
            'to': str,
            'requires_attention': bool
        }
        """

        # Input validation
        if not isinstance(amount, (int, float)) or amount < 0:
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'INVALID_AMOUNT',
                'error_data': {'amount': amount, 'message': 'Amount must be a positive number'},
                'conversion_type': 'failed',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': False
            }

        if not from_unit or not isinstance(from_unit, str):
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'INVALID_FROM_UNIT',
                'error_data': {'from_unit': from_unit, 'message': 'Invalid source unit'},
                'conversion_type': 'failed',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': False
            }

        if not to_unit or not isinstance(to_unit, str):
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'INVALID_TO_UNIT',
                'error_data': {'to_unit': to_unit, 'message': 'Invalid target unit'},
                'conversion_type': 'failed',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': False
            }

        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()

        if not from_u:
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'UNKNOWN_SOURCE_UNIT',
                'error_data': {'unit': from_unit, 'message': f'Unit "{from_unit}" not found in system'},
                'conversion_type': 'failed',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': False
            }

        if not to_u:
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'UNKNOWN_TARGET_UNIT',
                'error_data': {'unit': to_unit, 'message': f'Unit "{to_unit}" not found in system'},
                'conversion_type': 'failed',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': False
            }

        conversion_type = 'unknown'
        used_density = None
        converted = None

        # 1. Custom Mapping (including compound and cross-type)
        def find_conversion_path(start, end, visited=None):
            if visited is None:
                visited = set()
            if start == end:
                return []
            if start in visited:
                return None
            visited.add(start)

            # Check direct mappings (both directions) with organization scoping
            if current_user and current_user.is_authenticated and current_user.organization_id:
                forward_mappings = CustomUnitMapping.query.filter_by(
                    from_unit=start, 
                    organization_id=current_user.organization_id
                ).all()
                reverse_mappings = CustomUnitMapping.query.filter_by(
                    to_unit=start, 
                    organization_id=current_user.organization_id
                ).all()
            else:
                # For unauthenticated users or developers, check all mappings
                forward_mappings = CustomUnitMapping.query.filter_by(from_unit=start).all()
                reverse_mappings = CustomUnitMapping.query.filter_by(to_unit=start).all()

            # Try forward mappings
            for mapping in forward_mappings:
                if mapping.to_unit == end:
                    return [mapping]
                path = find_conversion_path(mapping.to_unit, end, visited.copy())
                if path is not None:
                    return [mapping] + path

            # Try reverse mappings (with inverted conversion factor)
            for mapping in reverse_mappings:
                if mapping.from_unit == end:
                    # Create a reverse mapping object
                    reverse_mapping = type('obj', (object,), {
                        'from_unit': mapping.to_unit,
                        'to_unit': mapping.from_unit,
                        'conversion_factor': 1.0 / mapping.conversion_factor
                    })()
                    return [reverse_mapping]
                path = find_conversion_path(mapping.from_unit, end, visited.copy())
                if path is not None:
                    reverse_mapping = type('obj', (object,), {
                        'from_unit': mapping.to_unit,
                        'to_unit': mapping.from_unit,
                        'conversion_factor': 1.0 / mapping.conversion_factor
                    })()
                    return [reverse_mapping] + path

            return None

        conversion_path = find_conversion_path(from_unit, to_unit)
        if conversion_path:
            converted = amount
            for mapping in conversion_path:
                converted *= mapping.conversion_factor
            conversion_type = 'custom_compound' if len(conversion_path) > 1 else 'custom'

        # 2. Direct (same unit)
        elif from_unit == to_unit:
            converted = amount
            conversion_type = 'direct'

        # 3. Same-type base conversion (volume → volume, weight → weight)
        elif from_u.unit_type == to_u.unit_type:
            if from_unit == to_unit:
                converted = amount
            else:
                try:
                    from_multiplier = float(from_u.conversion_factor) if from_u.conversion_factor else 1.0
                    to_multiplier = float(to_u.conversion_factor) if to_u.conversion_factor else 1.0
                    base_amount = amount * from_multiplier
                    converted = base_amount / to_multiplier
                except (ValueError, TypeError, ZeroDivisionError) as e:
                    return {
                        'success': False,
                        'converted_value': None,
                        'error_code': 'CONVERSION_ERROR',
                        'error_data': {'from_unit': from_unit, 'to_unit': to_unit, 'message': str(e)},
                        'conversion_type': 'failed',
                        'density_used': None,
                        'from': from_unit,
                        'to': to_unit,
                        'requires_attention': False
                    }
            conversion_type = 'direct'

        # 4. Cross-type: volume ↔ weight
        elif {'volume', 'weight'} <= {from_u.unit_type, to_u.unit_type}:
            # Only use ingredient-level density
            if density is None and ingredient_id:
                ingredient = Ingredient.query.get(ingredient_id)
                if ingredient and ingredient.density:
                    density = ingredient.density
            if density is None:
                # Get ingredient name for better error context
                ingredient_name = None
                if ingredient_id:
                    ingredient = Ingredient.query.get(ingredient_id)
                    if ingredient:
                        ingredient_name = ingredient.name
                
                # Improved error handling for missing density
                return {
                    'success': False,
                    'converted_value': None,
                    'error_code': 'MISSING_DENSITY',
                    'error_data': {
                        'from_unit': from_unit, 
                        'to_unit': to_unit, 
                        'ingredient_id': ingredient_id,
                        'ingredient_name': ingredient_name,
                        'message': f"Missing density for conversion from {from_unit} ({from_u.unit_type}) to {to_unit} ({to_u.unit_type}). Please set ingredient density or add a custom unit mapping."
                    },
                    'conversion_type': 'density',
                    'density_used': None,
                    'from': from_unit,
                    'to': to_unit,
                    'requires_attention': True
                }
            used_density = density

            try:
                if from_u.unit_type == 'volume':
                    grams = amount * from_u.conversion_factor * density
                    converted = grams / to_u.conversion_factor
                else:  # weight → volume
                    ml = (amount * from_u.conversion_factor) / density
                    converted = ml / to_u.conversion_factor
                conversion_type = 'density'
            except (ValueError, TypeError, ZeroDivisionError) as e:
                return {
                    'success': False,
                    'converted_value': None,
                    'error_code': 'DENSITY_CONVERSION_ERROR',
                    'error_data': {'from_unit': from_unit, 'to_unit': to_unit, 'message': str(e)},
                    'conversion_type': 'density',
                    'density_used': used_density,
                    'from': from_unit,
                    'to': to_unit,
                    'requires_attention': True
                }

        # 5. Check for custom cross-type mappings (e.g., count ↔ volume/weight)
        elif from_u.is_custom or to_u.is_custom:
            # Try to find a custom mapping path
            conversion_path = find_conversion_path(from_unit, to_unit)
            if conversion_path:
                converted = amount
                for mapping in conversion_path:
                    converted *= mapping.conversion_factor
                conversion_type = 'custom_cross_type'
            else:
                return {
                    'success': False,
                    'converted_value': None,
                    'error_code': 'MISSING_CUSTOM_MAPPING',
                    'error_data': {'from_unit': from_unit, 'to_unit': to_unit, 'message': f"Cannot convert {from_unit} ({from_u.unit_type}) to {to_unit} ({to_u.unit_type}) without a custom mapping. Go to Unit Manager to create a mapping."},
                    'conversion_type': 'custom',
                    'density_used': None,
                    'from': from_unit,
                    'to': to_unit,
                    'requires_attention': True
                }
        else:
            return {
                'success': False,
                'converted_value': None,
                'error_code': 'UNSUPPORTED_CONVERSION',
                'error_data': {'from_unit': from_unit, 'to_unit': to_unit, 'message': f"Cannot convert {from_unit} ({from_u.unit_type}) to {to_unit} ({to_u.unit_type}) without a custom mapping. Go to Unit Manager to create a mapping."},
                'conversion_type': 'unknown',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': True
            }

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
                # Decide if this should be a user-facing error or logged internally
                # For now, we'll just print and continue if logging fails.

        # Return structured metadata with consistent rounding
        return {
            'success': True,
            'converted_value': ConversionEngine.round_value(converted, 3),
            'conversion_type': conversion_type,
            'density_used': used_density,
            'from': from_unit,
            'to': to_unit,
            'requires_attention': conversion_type in ['custom', 'density'] # Adjust this based on desired attention flags
        }
