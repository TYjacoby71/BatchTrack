
from datetime import datetime, timezone
import pytz
from flask import current_app
from flask_login import current_user

class TimezoneUtils:
    """Centralized timezone handling for the application"""
    
    @staticmethod
    def get_user_timezone():
        """Get user's configured timezone, default to Eastern Time"""
        try:
            if current_user.is_authenticated and current_user.timezone:
                return pytz.timezone(current_user.timezone)
            else:
                return pytz.timezone('America/New_York')  # Default Eastern Time
        except:
            return timezone.utc  # Fallback to UTC
    
    @staticmethod
    def get_organization_timezone():
        """Get organization's default timezone"""
        # For multi-user organizations, you might want a default org timezone
        # For now, use Eastern Time as default
        try:
            return pytz.timezone('America/New_York')
        except:
            return timezone.utc
    
    @staticmethod
    def now():
        """Get current time in user's timezone"""
        return datetime.now(TimezoneUtils.get_user_timezone())
    
    @staticmethod
    def now_naive():
        """Get current time as timezone-naive datetime for template comparisons"""
        user_tz = TimezoneUtils.get_user_timezone()
        return datetime.now(user_tz).replace(tzinfo=None)
    
    @staticmethod
    def utc_now():
        """Get current UTC time (for database storage) - ALL database writes should use this"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_user_timezone(dt):
        """Convert datetime to user's timezone for display"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume UTC if no timezone info (all DB times should be UTC)
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TimezoneUtils.get_user_timezone())
    
    @staticmethod
    def to_utc(dt):
        """Convert datetime to UTC for database storage"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume user's timezone if no timezone info
            user_tz = TimezoneUtils.get_user_timezone()
            dt = dt.replace(tzinfo=user_tz)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def format_for_user(dt, format_string='%Y-%m-%d %H:%M:%S'):
        """Format datetime for user display in their timezone"""
        if dt is None:
            return ""
        user_dt = TimezoneUtils.to_user_timezone(dt)
        return user_dt.strftime(format_string)
    
    @staticmethod
    def get_available_timezones():
        """Get list of common timezones for user selection"""
        return [
            'US/Pacific',
            'US/Mountain', 
            'US/Central',
            'US/Eastern',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'UTC'
        ]
