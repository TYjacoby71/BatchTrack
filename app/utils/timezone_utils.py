import pytz
from typing import Dict, List, Tuple
from datetime import datetime

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
    def get_grouped_timezones() -> Dict[str, List[Tuple[str, str]]]:
        """Get timezones grouped by region with display names"""
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

        for tz_name in priority_timezones:
            if tz_name in pytz.all_timezones:
                display_name = TimezoneUtils.TIMEZONE_ALIASES.get(tz_name, tz_name)
                region = TimezoneUtils._get_timezone_region(tz_name)
                grouped[region].append((tz_name, display_name))

        # Add other common timezones
        for tz_name in sorted(pytz.common_timezones):
            if tz_name not in priority_timezones:
                display_name = TimezoneUtils._format_timezone_display(tz_name)
                region = TimezoneUtils._get_timezone_region(tz_name)
                grouped[region].append((tz_name, display_name))

        # Remove empty regions
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