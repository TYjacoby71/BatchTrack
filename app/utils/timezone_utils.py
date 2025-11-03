import pytz
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timezone

class TimezoneUtils:
    """Industry-standard timezone utilities using pytz"""

    # Common timezone aliases for user-friendly display
    TIMEZONE_ALIASES = {
        'US/Eastern': 'Eastern Time (US)',
        'US/Central': 'Central Time (US)', 
        'US/Mountain': 'Mountain Time (US)',
        'US/Pacific': 'Pacific Time (US)',
        'US/Alaska': 'Alaska Time (US)',
        'US/Hawaii': 'Hawaii Time (US)',
        'Europe/London': 'Greenwich Mean Time',
        'Europe/Paris': 'Central European Time',
        'Europe/Berlin': 'Central European Time',
        'Europe/Rome': 'Central European Time',
        'Europe/Madrid': 'Central European Time',
        'Europe/Amsterdam': 'Central European Time',
        'Asia/Tokyo': 'Japan Standard Time',
        'Asia/Shanghai': 'China Standard Time',
        'Asia/Kolkata': 'India Standard Time',
        'Asia/Dubai': 'Gulf Standard Time',
        'Australia/Sydney': 'Australian Eastern Time',
        'Australia/Melbourne': 'Australian Eastern Time',
        'Australia/Perth': 'Australian Western Time',
        'Canada/Eastern': 'Eastern Time (Canada)',
        'Canada/Central': 'Central Time (Canada)',
        'Canada/Mountain': 'Mountain Time (Canada)',
        'Canada/Pacific': 'Pacific Time (Canada)'
    }

    @staticmethod
    def get_available_timezones() -> List[str]:
        """Get all available pytz timezones"""
        return list(pytz.all_timezones)

    @staticmethod
    def get_common_timezones() -> List[str]:
        """Get commonly used timezones"""
        return list(pytz.common_timezones)

    @staticmethod
    def get_grouped_timezones(detected_timezone: str = None) -> Dict[str, List[Tuple[str, str]]]:
        """Get timezones grouped by region with display names
        
        Args:
            detected_timezone: Auto-detected timezone to show at top with related zones
        """
        grouped = {
            'North America': [],
            'Europe': [],
            'Asia': [],
            'Australia/Pacific': [],
            'Africa': [],
            'South America': [],
            'Other': []
        }

        # Priority timezones (most commonly used)
        priority_timezones = [
            'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
            'Europe/London', 'Europe/Paris', 'Europe/Berlin',
            'Asia/Tokyo', 'Asia/Shanghai', 'Australia/Sydney'
        ]
        
        # If we have a detected timezone, add it and related zones to top
        if detected_timezone and detected_timezone in pytz.all_timezones:
            grouped['🌍 Suggested (Based on Your Location)'] = []
            
            # Add detected timezone first
            display_name = TimezoneUtils._format_timezone_display(detected_timezone)
            grouped['🌍 Suggested (Based on Your Location)'].append((detected_timezone, f"✓ {display_name} (Detected)"))
            
            # Add 4 related timezones from same region
            detected_region = TimezoneUtils._get_timezone_region(detected_timezone)
            related_count = 0
            for tz_name in sorted(pytz.all_timezones):
                if related_count >= 4:
                    break
                if tz_name != detected_timezone and TimezoneUtils._get_timezone_region(tz_name) == detected_region:
                    display_name = TimezoneUtils._format_timezone_display(tz_name)
                    grouped['🌍 Suggested (Based on Your Location)'].append((tz_name, display_name))
                    related_count += 1

        for tz_name in priority_timezones:
            if tz_name in pytz.all_timezones:
                display_name = TimezoneUtils.TIMEZONE_ALIASES.get(tz_name, tz_name)
                region = TimezoneUtils._get_timezone_region(tz_name)
                grouped[region].append((tz_name, display_name))

        # Add ALL other timezones (not just common ones)
        for tz_name in sorted(pytz.all_timezones):
            if tz_name not in priority_timezones and (not detected_timezone or tz_name != detected_timezone):
                display_name = TimezoneUtils._format_timezone_display(tz_name)
                region = TimezoneUtils._get_timezone_region(tz_name)
                # Skip if already in suggested section
                if detected_timezone and tz_name in [tz[0] for tz in grouped.get('🌍 Suggested (Based on Your Location)', [])]:
                    continue
                grouped[region].append((tz_name, display_name))

        # Remove empty regions and return
        return {region: timezones for region, timezones in grouped.items() if timezones}

    @staticmethod
    def _get_timezone_region(tz_name: str) -> str:
        """Determine the region for a timezone"""
        if tz_name.startswith(('US/', 'Canada/', 'America/')):
            return 'North America'
        elif tz_name.startswith('Europe/'):
            return 'Europe'
        elif tz_name.startswith('Asia/'):
            return 'Asia'
        elif tz_name.startswith(('Australia/', 'Pacific/')):
            return 'Australia/Pacific'
        elif tz_name.startswith('Africa/'):
            return 'Africa'
        elif tz_name.startswith('South_America/'):
            return 'South America'
        else:
            return 'Other'

    @staticmethod
    def _format_timezone_display(tz_name: str) -> str:
        """Format timezone name for display"""
        if tz_name in TimezoneUtils.TIMEZONE_ALIASES:
            return TimezoneUtils.TIMEZONE_ALIASES[tz_name]

        # Format city names nicely
        parts = tz_name.split('/')
        if len(parts) >= 2:
            city = parts[-1].replace('_', ' ')
            region = parts[0].replace('_', ' ')
            return f"{city} ({region})"

        return tz_name.replace('_', ' ')

    @staticmethod
    def format_timezone_display(tz_name: str) -> str:
        """Public method to format timezone name for display - for template use"""
        return TimezoneUtils._format_timezone_display(tz_name)

    @staticmethod
    def validate_timezone(tz_name: str) -> bool:
        """Validate if timezone exists in pytz"""
        return tz_name in pytz.all_timezones

    @staticmethod
    def convert_time(dt: datetime, from_tz: str, to_tz: str) -> datetime:
        """Convert datetime from one timezone to another"""
        if not TimezoneUtils.validate_timezone(from_tz) or not TimezoneUtils.validate_timezone(to_tz):
            raise ValueError("Invalid timezone")

        from_timezone = pytz.timezone(from_tz)
        to_timezone = pytz.timezone(to_tz)

        # Localize the datetime to the source timezone
        localized_dt = from_timezone.localize(dt) if dt.tzinfo is None else dt.astimezone(from_timezone)

        # Convert to target timezone
        return localized_dt.astimezone(to_timezone)

    @staticmethod
    def convert_to_timezone(dt: datetime, to_timezone: str, assume_utc: bool = True) -> datetime:
        """Backward-compatible helper that converts *dt* to *to_timezone*."""
        if dt is None:
            return None

        if not to_timezone or not TimezoneUtils.validate_timezone(to_timezone):
            to_timezone = 'UTC'

        if dt.tzinfo is None:
            if not assume_utc:
                raise ValueError("Naive datetime provided without timezone; set assume_utc=True to treat as UTC")
            dt = dt.replace(tzinfo=timezone.utc)

        target_tz = pytz.timezone(to_timezone)
        return dt.astimezone(target_tz)

    @staticmethod
    def get_user_timezone_display(user_timezone: str) -> str:
        """Get display-friendly timezone name for user"""
        if not user_timezone:
            return 'UTC (Default)'

        return TimezoneUtils._format_timezone_display(user_timezone)

    @staticmethod
    def get_utc_offset(tz_name: str) -> str:
        """Get UTC offset string for timezone (e.g., '+05:30')"""
        if not TimezoneUtils.validate_timezone(tz_name):
            return '+00:00'

        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        offset = now.strftime('%z')

        # Format as +HH:MM
        if len(offset) == 5:
            return f"{offset[:3]}:{offset[3:]}"

        return '+00:00'

    @staticmethod
    def utc_now() -> datetime:
        """Get current UTC datetime - ALWAYS use this for database storage
        
        Returns timezone-aware UTC datetime for proper timezone handling.
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def now() -> datetime:
        """Get current datetime in user's timezone - for display only"""
        from flask_login import current_user
        
        utc_now = TimezoneUtils.utc_now()
        
        # Get user's timezone
        user_timezone = 'UTC'
        if current_user and current_user.is_authenticated:
            user_timezone = getattr(current_user, 'timezone', 'UTC')
        
        return TimezoneUtils.to_user_timezone(utc_now, user_timezone)

    @staticmethod
    def get_user_timezone() -> str:
        """Get current user's timezone"""
        from flask_login import current_user
        
        if current_user and current_user.is_authenticated:
            return getattr(current_user, 'timezone', 'UTC')
        return 'UTC'

    @staticmethod
    def to_user_timezone(dt: datetime, user_timezone: str = None) -> datetime:
        """Convert UTC datetime to user's timezone - for display only"""
        from flask_login import current_user
        
        if not dt:
            return dt
            
        # Get user's timezone
        if not user_timezone and current_user and current_user.is_authenticated:
            user_timezone = getattr(current_user, 'timezone', 'UTC')
        
        if not user_timezone or not TimezoneUtils.validate_timezone(user_timezone):
            user_timezone = 'UTC'
        
        # Convert UTC to user timezone
        utc_dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
        user_tz = pytz.timezone(user_timezone)
        return utc_dt.astimezone(user_tz)

    @staticmethod
    def from_user_timezone(dt: datetime, user_timezone: str = None) -> datetime:
        """Convert user timezone datetime to UTC - for storage"""
        from flask_login import current_user
        
        if not dt:
            return dt
            
        # Get user's timezone
        if not user_timezone and current_user and current_user.is_authenticated:
            user_timezone = getattr(current_user, 'timezone', 'UTC')
        
        if not user_timezone or not TimezoneUtils.validate_timezone(user_timezone):
            user_timezone = 'UTC'
        
        # Convert to UTC (keep timezone-aware)
        user_tz = pytz.timezone(user_timezone)
        user_dt = user_tz.localize(dt) if dt.tzinfo is None else dt
        return user_dt.astimezone(timezone.utc)

    @staticmethod
    def format_for_user(dt: datetime, format_string: str = '%Y-%m-%d %H:%M:%S', user_timezone: str = None) -> str:
        """Format datetime in user's timezone"""
        if not dt:
            return ''
            
        user_dt = TimezoneUtils.to_user_timezone(dt, user_timezone)
        return user_dt.strftime(format_string)
    
    @staticmethod
    def ensure_timezone_aware(dt: datetime, assume_utc: bool = True) -> datetime:
        """
        Ensure a datetime is timezone-aware.
        Prevents TypeError when comparing datetimes from database.
        
        Args:
            dt: The datetime to check
            assume_utc: If True and datetime is naive, assume it's UTC (default: True)
            
        Returns:
            Timezone-aware datetime
        """
        if dt is None:
            return None
            
        if dt.tzinfo is None:
            # Naive datetime - add timezone
            if assume_utc:
                return dt.replace(tzinfo=timezone.utc)
            else:
                raise ValueError("Naive datetime provided without explicit timezone handling")
        
        return dt
    
    @staticmethod
    def safe_datetime_compare(dt1: datetime, dt2: datetime, assume_utc: bool = True) -> bool:
        """
        Safely compare two datetimes, handling timezone-aware and naive datetimes.
        Prevents TypeError when comparing database datetimes with datetime.now(timezone.utc).
        
        Args:
            dt1: First datetime
            dt2: Second datetime
            assume_utc: If True, treat naive datetimes as UTC (default: True)
            
        Returns:
            True if dt1 > dt2
        """
        if dt1 is None or dt2 is None:
            return False
            
        # Ensure both are timezone-aware
        dt1 = TimezoneUtils.ensure_timezone_aware(dt1, assume_utc)
        dt2 = TimezoneUtils.ensure_timezone_aware(dt2, assume_utc)
        
        return dt1 > dt2
    
    @staticmethod
    def format_datetime_for_api(dt: datetime, user_timezone: str = None) -> Dict[str, str]:
        """
        Format datetime for API response with BOTH UTC and user timezone.
        Ensures APIs clearly distinguish between storage and display formats.
        
        Args:
            dt: Datetime to format (should be timezone-aware UTC)
            user_timezone: Optional user timezone (defaults to current_user.timezone)
            
        Returns:
            Dictionary with 'utc', 'local', 'display', and 'timezone' keys
        """
        if dt is None:
            return {'utc': None, 'local': None, 'display': None, 'timezone': None}
        
        from flask_login import current_user
        
        # Ensure datetime is timezone-aware
        dt = TimezoneUtils.ensure_timezone_aware(dt)
        
        # Get user timezone
        if not user_timezone:
            user_timezone = TimezoneUtils.get_user_timezone() if current_user and current_user.is_authenticated else 'UTC'
        
        # Convert to user timezone
        user_dt = TimezoneUtils.to_user_timezone(dt, user_timezone)
        
        return {
            'utc': dt.isoformat(),  # Always include UTC with explicit timezone
            'local': user_dt.isoformat(),  # User's timezone with explicit offset
            'display': user_dt.strftime('%b %d, %Y %I:%M %p %Z'),  # Human-readable
            'timezone': user_timezone  # Make timezone explicit
        }