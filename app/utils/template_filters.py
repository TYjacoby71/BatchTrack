from flask import current_app
from flask_login import current_user
from .timezone_utils import TimezoneUtils
from flask import Blueprint
from datetime import datetime, timedelta
import json
from ..models import Unit, User, Organization
from ..services.unit_conversion import ConversionEngine
from ..utils.unit_utils import get_global_unit_list
from ..utils.timezone_utils import TimezoneUtils
import re
import pytz

def register_template_filters(app):
    """Register all template filters"""

    @app.template_global('get_organization_by_id')
    def get_organization_by_id(org_id):
        """Get organization by ID for template use"""
        if org_id:
            return Organization.query.get(org_id)
        return None

    @app.template_filter('user_timezone')
    def user_timezone_filter(dt, format='%Y-%m-%d %H:%M'):
        """Convert UTC datetime to user's timezone and format it"""
        if not dt:
            return ''
        try:
            user_dt = TimezoneUtils.to_user_timezone(dt)
            return user_dt.strftime(format)
        except:
            return dt.strftime(format) if dt else ''

def register_filters(app):
    """Register custom template filters"""

    @app.template_filter('timestamp_to_date')
    def timestamp_to_date(timestamp):
        """Convert Unix timestamp to readable date"""
        if not timestamp:
            return 'N/A'
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            else:
                dt = timestamp
            return dt.strftime('%B %d, %Y')
        except (ValueError, TypeError):
            return 'Invalid date'

    @app.template_filter('user_datetime')
    def user_datetime(dt, format_string='%Y-%m-%d %H:%M:%S'):
        """Format datetime in user's timezone"""
        if not dt:
            return ''
        return TimezoneUtils.format_for_user(dt, format_string)

    @app.template_filter('user_date')
    def user_date(dt):
        """Format date in user's timezone"""
        if not dt:
            return ''
        return TimezoneUtils.format_for_user(dt, '%Y-%m-%d')

    @app.template_filter('user_time')
    def user_time(dt):
        """Format time in user's timezone"""
        if not dt:
            return ''
        return TimezoneUtils.format_for_user(dt, '%H:%M:%S')

    @app.template_filter('from_symbol')
    def from_symbol_filter(symbol):
        """Get unit object from symbol"""
        try:
            engine = ConversionEngine()
            return engine.get_unit_by_symbol(symbol)
        except:
            return None

    @app.template_filter('format_user_time')
    def format_user_time_filter(dt, format_string='%Y-%m-%d %H:%M:%S'):
        """Format datetime for user's timezone"""
        if not dt:
            return ''
        return TimezoneUtils.format_for_user(dt, format_string)

    @app.template_filter('to_user_tz')
    def to_user_timezone_filter(dt):
        """Convert datetime to user's timezone"""
        if not dt:
            return dt
        return TimezoneUtils.to_user_timezone(dt)

    @app.template_global()
    def TimezoneUtils_global():
        """Make TimezoneUtils available globally in templates"""
        return TimezoneUtils

    @app.template_global()
    def get_grouped_timezones():
        """Get grouped timezones for dropdowns"""
        return TimezoneUtils.get_grouped_timezones()

    @app.template_global()
    def get_available_timezones():
        """Get all available timezones"""
        return TimezoneUtils.get_available_timezones()

    @app.template_global()
    def is_organization_owner():
        """Check if current user is organization owner (but still respects subscription limits)"""
        if not current_user.is_authenticated:
            return False

        if current_user.user_type == 'developer':
            return True  # Developers can act as owners

        if not current_user.organization_id:
            return False

        organization = Organization.query.get(current_user.organization_id)
        return organization and organization.owner_id == current_user.id

    @app.template_global()
    def has_permission(permission_name):
        """Template function to check if current user has permission"""
        if not current_user or not current_user.is_authenticated:
            return False
        from app.utils import permissions as permission_utils
        return permission_utils.has_permission(current_user, permission_name)

    @app.template_global()
    def has_tier_permission(permission_name):
        """Template function to check if current user's subscription tier allows permission"""
        if not current_user or not current_user.is_authenticated:
            return False
        from app.utils import permissions as permission_utils
        return permission_utils._has_tier_permission(current_user, permission_name)

    @app.template_global()
    def get_current_tier():
        """Template function to get current user's subscription tier"""
        if not current_user or not current_user.is_authenticated or not current_user.organization:
            return 'free'
        return current_user.organization.effective_subscription_tier

    @app.template_global()
    def get_tier_features(tier_key=None):
        """Get features for a subscription tier from DB permissions only"""
        try:
            if not tier_key:
                tier_key = get_current_tier()
            from app.models.subscription_tier import SubscriptionTier
            try:
                tier_id = int(tier_key)
            except (TypeError, ValueError):
                tier_id = None
            tier = SubscriptionTier.query.get(tier_id) if tier_id is not None else None
            if not tier:
                return []
            return [p.name for p in getattr(tier, 'permissions', [])]
        except Exception:
            return []

    @app.template_filter('user_timezone')
    def user_timezone_filter(datetime_obj, format_string='%Y-%m-%d %H:%M:%S'):
        """Convert UTC datetime to user's timezone for display"""
        if datetime_obj is None:
            return ''

        # Convert UTC to user's timezone
        user_time = TimezoneUtils.to_user_timezone(datetime_obj)
        return user_time.strftime(format_string)

# Define unit conversion logic here
def register_unit_converter_filters(app):
    """Register filters and globals for the unit converter"""

    # Add missing TimezoneUtils import if not already present
    try:
        from .timezone_utils import TimezoneUtils
    except ImportError:
        # Assuming timezone_utils is in the same directory or accessible path
        from app.utils.timezone_utils import TimezoneUtils # Adjust path if necessary

    @app.template_filter('get_unit_by_symbol')
    def get_unit_by_symbol_filter(symbol):
        """Get unit object from symbol"""
        try:
            engine = ConversionEngine()
            return engine.get_unit_by_symbol(symbol)
        except Exception as e:
            print(f"Error getting unit by symbol '{symbol}': {e}")
            return None

    @app.template_filter('get_ingredient_by_id')
    def get_ingredient_by_id_filter(ingredient_id):
        """Get ingredient object from ID"""
        try:
            from app.models.ingredient import Ingredient
            return Ingredient.query.get(ingredient_id)
        except Exception as e:
            print(f"Error getting ingredient by ID '{ingredient_id}': {e}")
            return None

    @app.template_global('get_all_global_units')
    def get_all_global_units_global():
        """Get all global units for selection"""
        return get_global_unit_list()

    @app.template_global('get_user_inventory_ingredients')
    def get_user_inventory_ingredients_global():
        """Get user's inventory ingredients for selection"""
        if not current_user.is_authenticated:
            return []
        try:
            from app.models.ingredient import Ingredient
            return Ingredient.query.filter_by(owner_id=current_user.id).all()
        except Exception as e:
            print(f"Error getting user inventory ingredients: {e}")
            return []

    # Add filters from the second block that are relevant to the unit converter
    @app.template_filter('attr_multiply')
    def attr_multiply_filter(item, attr1, attr2):
        if item is None:
            return 0
        val1 = getattr(item, attr1, 0) or 0
        val2 = getattr(item, attr2, 0) or 0
        return float(val1) * float(val2)

    @app.template_filter('format_datetime')
    def format_datetime(dt):
        if dt is None:
            return 'Never'
        # Convert to user's timezone
        user_tz = 'UTC'
        if current_user.is_authenticated and current_user.timezone:
            user_tz = current_user.timezone
        local_dt = TimezoneUtils.convert_to_timezone(dt, user_tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

    # Add helper function for density conversion
    @app.template_global('convert_density')
    def convert_density(value, from_unit_symbol, to_unit_symbol, ingredient_id=None):
        """Convert value between units, considering density if needed"""
        engine = ConversionEngine()
        try:
            from_unit = engine.get_unit_by_symbol(from_unit_symbol)
            to_unit = engine.get_unit_by_symbol(to_unit_symbol)

            if not from_unit or not to_unit:
                return None # Or raise an error

            # Check if density is required for the conversion
            # This logic needs to be robust. It might involve checking unit categories or specific flags.
            # For now, let's assume a simple check based on common density-related units or if ingredient_id is provided.
            requires_density = False
            if ingredient_id:
                requires_density = True
            elif from_unit.category == 'mass' and to_unit.category == 'volume':
                requires_density = True
            elif from_unit.category == 'volume' and to_unit.category == 'mass':
                requires_density = True

            if requires_density and ingredient_id:
                ingredient = get_ingredient_by_id_filter(ingredient_id)
                if ingredient and ingredient.density is not None:
                    # Assume density is in kg/L or similar standard unit
                    # Need to ensure units are compatible or perform intermediate conversions
                    # This is a simplified example
                    density = ingredient.density
                    # Example: Convert mass to volume: value (mass) / density (mass/volume) = volume
                    # Example: Convert volume to mass: value (volume) * density (mass/volume) = mass
                    # This requires a more sophisticated understanding of the unit system and density units.
                    # For now, let's return None or an indicative value if density is needed but not available or handled.
                    return None # Placeholder for actual density-based conversion logic
                else:
                    return None # Ingredient or its density not found
            else:
                # Perform standard unit conversion
                return engine.convert(value, from_unit_symbol, to_unit_symbol)

        except Exception as e:
            print(f"Error during density conversion: {e}")
            return None

    # Add filters from the second block that were previously in register_template_filters
    @app.template_filter('product_variant_name')
    def product_variant_name(item):
        # Placeholder implementation
        return str(item)

    @app.template_filter('ingredient_cost_currency')
    def ingredient_cost_currency(item):
        # Placeholder implementation
        return str(item)

    @app.template_filter('safe_float')
    def safe_float(value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # Simplified user_date and user_timezone for direct use if TimezoneUtils is complex
    @app.template_filter('user_date_simple')
    def user_date_simple(dt, format_string='%Y-%m-%d'):
        """Format date for user display (simplified)"""
        if not dt:
            return 'N/A'
        try:
            return dt.strftime(format_string)
        except:
            return 'Invalid Date'

    @app.template_filter('user_time_simple')
    def user_time_simple(dt, format_string='%H:%M:%S'):
        """Format time for user display (simplified)"""
        if not dt:
            return 'N/A'
        try:
            return dt.strftime(format_string)
        except:
            return 'Invalid Time'

    # Explicitly register these if they were intended to be separate
    # Assuming these are meant to be available globally for templates
    app.jinja_env.globals.update({
        'get_unit_by_symbol': get_unit_by_symbol_filter,
        'get_ingredient_by_id': get_ingredient_by_id_filter,
        'get_all_global_units': get_all_global_units_global,
        'get_user_inventory_ingredients': get_user_inventory_ingredients_global,
        'convert_density': convert_density,
    })

    # Ensure filters from the second block are updated if they weren't already
    app.jinja_env.filters.update({
        'product_variant_name': product_variant_name,
        'ingredient_cost_currency': ingredient_cost_currency,
        'safe_float': safe_float,
        'user_date_simple': user_date_simple,
        'user_time_simple': user_time_simple,
    })