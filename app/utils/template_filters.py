
from flask import current_app
from .timezone_utils import TimezoneUtils

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
