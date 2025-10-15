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
        """Template function to get features for a subscription tier"""
        if not tier_key:
            tier_key = get_current_tier()

        from app.blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier_key, {})
        return tier_data.get('features', [])

    @app.template_filter('user_timezone')
    def user_timezone_filter(datetime_obj, format_string='%Y-%m-%d %H:%M:%S'):
        """Convert UTC datetime to user's timezone for display"""
        if datetime_obj is None:
            return ''

        # Convert UTC to user's timezone
        user_time = TimezoneUtils.to_user_timezone(datetime_obj)
        return user_time.strftime(format_string)
from flask_login import current_user
from .timezone_utils import TimezoneUtils

def register_template_filters(app):
    """Register all Jinja2 template filters"""
    
    from app.filters.product_filters import (
        product_variant_name, ingredient_cost_currency, safe_float,
        register_filters
    )

    # Register product filters
    register_filters(app)

    # Register custom filters
    app.jinja_env.filters.update({
        'product_variant_name': product_variant_name,
        'ingredient_cost_currency': ingredient_cost_currency,
        'safe_float': safe_float
    })

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

    # Register template globals
    from .permissions import (
        has_permission, has_role, has_subscription_feature, 
        is_organization_owner, is_developer
    )

    def template_has_permission(user_or_permission, permission_name=None):
        try:
            from flask_login import current_user
            from app.utils.permissions import has_permission as has_perm_util
            
            # Handle both calling patterns:
            # has_permission('inventory.adjust') - permission only
            # has_permission(current_user, 'inventory.adjust') - user + permission
            if permission_name is None:
                # Single argument - it's the permission name
                return has_perm_util(current_user, user_or_permission)
            else:
                # Two arguments - user and permission
                return has_perm_util(user_or_permission, permission_name)
        except Exception:
            return False

    def template_has_role(role_name):
        try:
            return has_role(role_name)
        except Exception:
            return False

    def template_is_org_owner():
        try:
            return is_organization_owner()
        except Exception:
            return False

    # Register globals
    app.jinja_env.globals.update({
        'has_permission': template_has_permission,
        'has_role': template_has_role,
        'has_subscription_feature': has_subscription_feature,
        'is_organization_owner': template_is_org_owner,
        'is_developer': is_developer,
        'can_access_route': lambda route_path: True,  # Deprecated but maintained
    })
