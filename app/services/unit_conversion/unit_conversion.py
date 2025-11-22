from datetime import datetime
import logging
from flask import session
from flask_login import current_user
from ...models import db, Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog
from .drawer_errors import handle_conversion_error
from ...utils.cache_manager import conversion_cache

class ConversionEngine:
    """
    Enhanced Unit Conversion Engine
    Handles direct conversions, density-based conversions, and custom mappings
    """

    # ConversionEngine uses centralized app cache in cache_manager

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
    def convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None, organization_id=None):
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

        # Determine effective organization for scoping (developer view respected)
        effective_org_id = organization_id
        try:
            if effective_org_id is None and current_user and current_user.is_authenticated:
                if getattr(current_user, 'user_type', None) == 'developer':
                    effective_org_id = session.get('dev_selected_org_id')
                else:
                    effective_org_id = current_user.organization_id
        except Exception:
            # Fallback to provided organization_id only
            pass

        # Create cache key (org-scoped)
        cache_key = f"org:{effective_org_id or 'public'}:{amount}:{from_unit}:{to_unit}:{ingredient_id}:{density}"

        # Check centralized cache first
        cached_result = conversion_cache.get(cache_key)
        if cached_result and cached_result.get('success'):
            return cached_result

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
            base_result = {
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
            drawer_info = handle_conversion_error(base_result)
            base_result.update(drawer_info)
            return base_result

        if not to_u:
            base_result = {
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
            drawer_info = handle_conversion_error(base_result)
            base_result.update(drawer_info)
            return base_result

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
                ingredient = db.session.get(Ingredient, ingredient_id)
                if ingredient and ingredient.density and ingredient.density > 0:
                    density = ingredient.density
            # Hard guard: density must be > 0
            if density is None or (isinstance(density, (int, float)) and density <= 0):
                # Get ingredient name for better error context
                ingredient_name = None
                if ingredient_id:
                    ingredient = db.session.get(Ingredient, ingredient_id)
                    if ingredient:
                        ingredient_name = ingredient.name

                # Create base error result
                base_result = {
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

                # Use drawer error handler to add drawer-specific data
                drawer_info = handle_conversion_error(base_result)
                base_result.update(drawer_info)

                # If this error requires a drawer, dispatch it
                if drawer_info.get('requires_drawer') and drawer_info.get('drawer_payload'):
                    logging.getLogger(__name__).info(
                        "CONVERSION ENGINE: Dispatching drawer for %s",
                        base_result['error_code']
                    )
                    # The frontend will pick up this drawer_payload and trigger the drawer

                return base_result
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
                # Create base error result
                base_result = {
                    'success': False,
                    'converted_value': None,
                    'error_code': 'MISSING_CUSTOM_MAPPING',
                    'error_data': {
                        'from_unit': from_unit, 
                        'to_unit': to_unit, 
                        'message': f"Cannot convert {from_unit} ({from_u.unit_type}) to {to_unit} ({to_u.unit_type}) without a custom mapping. Go to Unit Manager to create a mapping."
                    },
                    'conversion_type': 'custom',
                    'density_used': None,
                    'from': from_unit,
                    'to': to_unit,
                    'requires_attention': True
                }

                # Use drawer error handler to add drawer-specific data
                drawer_info = handle_conversion_error(base_result)
                base_result.update(drawer_info)

                # If this error requires a drawer, dispatch it
                if drawer_info.get('requires_drawer') and drawer_info.get('drawer_payload'):
                    logging.getLogger(__name__).info(
                        "CONVERSION ENGINE: Dispatching drawer for %s",
                        base_result['error_code']
                    )
                    # The frontend will pick up this drawer_payload and trigger the drawer

                return base_result
        else:
            # Create base error result
            base_result = {
                'success': False,
                'converted_value': None,
                'error_code': 'UNSUPPORTED_CONVERSION',
                'error_data': {
                    'from_unit': from_unit, 
                    'to_unit': to_unit, 
                    'message': f"Cannot convert {from_unit} ({from_u.unit_type}) to {to_unit} ({to_u.unit_type}) without a custom mapping. Go to Unit Manager to create a mapping."
                },
                'conversion_type': 'unknown',
                'density_used': None,
                'from': from_unit,
                'to': to_unit,
                'requires_attention': True
            }

            # Use drawer error handler to add drawer-specific data
            drawer_info = handle_conversion_error(base_result)
            base_result.update(drawer_info)

            # If this error requires a drawer, dispatch it
            if drawer_info.get('requires_drawer') and drawer_info.get('drawer_payload'):
                logging.getLogger(__name__).info(
                    "CONVERSION ENGINE: Dispatching drawer for %s",
                    base_result['error_code']
                )
                # The frontend will pick up this drawer_payload and trigger the drawer

            return base_result

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
                logging.getLogger(__name__).exception("Error logging conversion: %s", e)
                db.session.rollback()
                # Decide if this should be a user-facing error or logged internally
                # For now, we'll just print and continue if logging fails.

        # Return success result with all metadata
        result = {
            'success': True,
            'converted_value': ConversionEngine.round_value(converted, 3),
            'conversion_type': conversion_type,
            'density_used': used_density,
            'from': from_unit,
            'to': to_unit,
            'requires_attention': conversion_type in ['custom', 'density'] # Adjust this based on desired attention flags
        }

        # Cache successful result (1 hour TTL by default via conversion_cache)
        conversion_cache.set(cache_key, result)
        return result

    @staticmethod
    def can_convert_units(amount, from_unit, to_unit, ingredient_id=None, density=None, organization_id=None):
        """
        Lightweight capability check used by planners that don't have density context.
        Returns True when units are considered compatible (same unit or unit_type, or a custom mapping exists).
        """
        if not from_unit or not to_unit:
            return False

        try:
            from_u = Unit.query.filter_by(name=from_unit).first()
            to_u = Unit.query.filter_by(name=to_unit).first()
            if not from_u or not to_u:
                return False

            if from_u.name == to_u.name:
                return True

            from_type = (from_u.unit_type or "").lower()
            to_type = (to_u.unit_type or "").lower()
            if from_type and to_type and from_type == to_type:
                return True

            if from_u.base_unit and to_u.base_unit and from_u.base_unit == to_u.base_unit:
                return True

            # Check for a custom mapping that links the units (org-scoped when possible)
            effective_org_id = organization_id
            try:
                if effective_org_id is None and current_user and current_user.is_authenticated:
                    if getattr(current_user, 'user_type', None) == 'developer':
                        effective_org_id = session.get('dev_selected_org_id')
                    else:
                        effective_org_id = current_user.organization_id
            except Exception:
                effective_org_id = organization_id

            mapping_query = CustomUnitMapping.query.filter(
                ((CustomUnitMapping.from_unit == from_unit) & (CustomUnitMapping.to_unit == to_unit)) |
                ((CustomUnitMapping.from_unit == to_unit) & (CustomUnitMapping.to_unit == from_unit))
            )
            if effective_org_id:
                mapping_query = mapping_query.filter(
                    (CustomUnitMapping.organization_id == effective_org_id) |
                    (CustomUnitMapping.organization_id.is_(None))
                )

            return mapping_query.first() is not None
        except Exception:
            return False