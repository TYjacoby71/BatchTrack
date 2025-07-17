from flask import current_user
from flask import current_app
from .timezone_utils import TimezoneUtils
from flask import Blueprint
from datetime import datetime, timedelta
import json
from ..models import Unit
from ..services.unit_conversion import ConversionEngine
from ..utils.unit_utils import get_global_unit_list
from ..utils.timezone_utils import TimezoneUtils

def register_filters(app):
    """Register custom template filters"""

    @app.template_filter('user_datetime')
    def user_datetime(dt, format_string='%Y-%m-%d %H:%M:%S'):
        """Format datetime in user's timezone"""
        return TimezoneUtils.format_for_user(dt, format_string)

    @app.template_filter('user_date')
    def user_date(dt):
        """Format date in user's timezone"""
        return TimezoneUtils.format_for_user(dt, '%Y-%m-%d')

    @app.template_filter('user_time')
    def user_time(dt):
        """Format time in user's timezone"""
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
        return TimezoneUtils.format_for_user(dt, format_string)

    @app.template_filter('to_user_tz')
    def to_user_timezone_filter(dt):
        """Convert datetime to user's timezone"""
        return TimezoneUtils.to_user_timezone(dt)

    @app.template_global()
    def TimezoneUtils_global():
        """Make TimezoneUtils available globally in templates"""
        return TimezoneUtils

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
        """Template function to check if current user has a specific permission"""
        if not current_user.is_authenticated:
            return False

        # Use the centralized permission checking function
        from app.utils.permissions import has_permission as check_permission
        return check_permission(permission_name)