from flask import current_app
from flask_login import current_user
from .timezone_utils import TimezoneUtils
from flask import Blueprint
from datetime import datetime, timedelta
import json
from ..models import Unit
from ..services.unit_conversion import ConversionEngine
from ..utils.unit_utils import get_global_unit_list

def register_template_filters(app):
    """Register all template filters"""

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
        """Template function to check if current user is organization owner"""
        if not current_user.is_authenticated:
            return False

        # Developers in customer support mode act as organization owners
        if current_user.user_type == 'developer':
            from flask import session
            return session.get('dev_selected_org_id') is not None

        return current_user.user_type == 'organization_owner' or current_user.is_organization_owner

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
        return tier_data.get('fallback_features', [])