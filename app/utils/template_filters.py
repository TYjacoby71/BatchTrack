from flask import current_app
from flask_login import current_user
from .timezone_utils import TimezoneUtils
from flask import Blueprint
from datetime import datetime, timedelta
import json
from ..models import Unit
from ..services.unit_conversion import ConversionEngine
from ..utils.unit_utils import get_global_unit_list
from app.models.models import User
from app.models.permission import Permission
from app.models.role import Role
from flask_login import current_user
from flask import session
import logging

logger = logging.getLogger(__name__)

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
        """Template function to check if current user has a specific permission"""
        if not current_user.is_authenticated:
            return False

        # Use the centralized permission checking function
        from app.utils.permissions import has_permission as check_permission
        return check_permission(permission_name)

def register_template_helpers(app):
    """Register template helper functions"""

    @app.context_processor
    def inject_helpers():
        from app.services.subscription_features import SubscriptionFeatures

        return dict(
            TimezoneUtils_global=TimezoneUtils,
            has_permission=has_permission,
            has_role=has_role,
            is_organization_owner=is_organization_owner,
            get_user_display_name=get_user_display_name,
            has_subscription_feature=SubscriptionFeatures.has_feature,
            get_subscription_features=SubscriptionFeatures.get_available_features,
            get_upgrade_suggestions=SubscriptionFeatures.get_upgrade_suggestions
        )