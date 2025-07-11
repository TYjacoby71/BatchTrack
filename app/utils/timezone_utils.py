
from datetime import datetime, timezone
import pytz
from flask import current_app

class TimezoneUtils:
    """Centralized timezone handling for the application"""
    
    @staticmethod
    def get_user_timezone():
        """Get user's configured timezone, default to Pacific Time"""
        # You can extend this to get user's actual timezone from settings
        try:
            return pytz.timezone('America/Los_Angeles')  # Pacific Time
        except:
            return timezone.utc  # Fallback to UTC
    
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
        """Get current UTC time (for database storage)"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_user_timezone(dt):
        """Convert datetime to user's timezone for display"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume UTC if no timezone info
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
