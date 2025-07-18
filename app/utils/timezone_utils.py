
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
        """Get comprehensive list of industry-standard timezones organized by region"""
        # Get all pytz timezones and organize them by region
        all_timezones = list(pytz.all_timezones)
        
        # Filter out deprecated and uncommon zones, organize by region
        common_timezones = [
            # UTC first
            'UTC',
            
            # North America - Major Cities
            'America/New_York',      # Eastern Time
            'America/Chicago',       # Central Time  
            'America/Denver',        # Mountain Time
            'America/Los_Angeles',   # Pacific Time
            'America/Phoenix',       # Arizona (no DST)
            'America/Anchorage',     # Alaska
            'America/Honolulu',      # Hawaii
            'America/Toronto',       # Eastern Canada
            'America/Vancouver',     # Pacific Canada
            'America/Mexico_City',   # Central Mexico
            'America/Tijuana',       # Pacific Mexico
            
            # South America
            'America/Sao_Paulo',     # Brazil
            'America/Buenos_Aires',  # Argentina
            'America/Lima',          # Peru
            'America/Bogota',        # Colombia
            'America/Caracas',       # Venezuela
            
            # Europe
            'Europe/London',         # UK/Ireland
            'Europe/Paris',          # Central Europe
            'Europe/Berlin',         # Germany
            'Europe/Rome',           # Italy
            'Europe/Madrid',         # Spain
            'Europe/Amsterdam',      # Netherlands
            'Europe/Brussels',       # Belgium
            'Europe/Vienna',         # Austria
            'Europe/Prague',         # Czech Republic
            'Europe/Warsaw',         # Poland
            'Europe/Stockholm',      # Sweden
            'Europe/Oslo',           # Norway
            'Europe/Helsinki',       # Finland
            'Europe/Copenhagen',     # Denmark
            'Europe/Dublin',         # Ireland
            'Europe/Lisbon',         # Portugal
            'Europe/Athens',         # Greece
            'Europe/Istanbul',       # Turkey
            'Europe/Moscow',         # Russia
            'Europe/Kiev',           # Ukraine
            'Europe/Zurich',         # Switzerland
            
            # Asia Pacific
            'Asia/Tokyo',            # Japan
            'Asia/Shanghai',         # China
            'Asia/Hong_Kong',        # Hong Kong
            'Asia/Singapore',        # Singapore
            'Asia/Seoul',            # South Korea
            'Asia/Bangkok',          # Thailand
            'Asia/Jakarta',          # Indonesia
            'Asia/Manila',           # Philippines
            'Asia/Kuala_Lumpur',     # Malaysia
            'Asia/Taipei',           # Taiwan
            'Asia/Ho_Chi_Minh',      # Vietnam
            'Asia/Mumbai',           # India
            'Asia/Kolkata',          # India (same as Mumbai)
            'Asia/Karachi',          # Pakistan
            'Asia/Dhaka',            # Bangladesh
            'Asia/Dubai',            # UAE
            'Asia/Riyadh',           # Saudi Arabia
            'Asia/Tehran',           # Iran
            'Asia/Baghdad',          # Iraq
            'Asia/Jerusalem',        # Israel
            'Asia/Beirut',           # Lebanon
            'Asia/Damascus',         # Syria
            'Asia/Amman',            # Jordan
            
            # Australia & Oceania
            'Australia/Sydney',      # Eastern Australia
            'Australia/Melbourne',   # Victoria
            'Australia/Brisbane',    # Queensland
            'Australia/Perth',       # Western Australia
            'Australia/Adelaide',    # South Australia
            'Australia/Darwin',      # Northern Territory
            'Pacific/Auckland',      # New Zealand
            'Pacific/Honolulu',      # Hawaii
            'Pacific/Fiji',          # Fiji
            'Pacific/Guam',          # Guam
            
            # Africa
            'Africa/Cairo',          # Egypt
            'Africa/Lagos',          # Nigeria
            'Africa/Nairobi',        # Kenya
            'Africa/Johannesburg',   # South Africa
            'Africa/Casablanca',     # Morocco
            'Africa/Tunis',          # Tunisia
            'Africa/Algiers',        # Algeria
            'Africa/Accra',          # Ghana
            'Africa/Addis_Ababa',    # Ethiopia
            'Africa/Dar_es_Salaam',  # Tanzania
        ]
        
        # Verify all timezones exist in pytz
        verified_timezones = []
        for tz in common_timezones:
            try:
                pytz.timezone(tz)
                verified_timezones.append(tz)
            except pytz.UnknownTimeZoneError:
                continue
        
        return verified_timezones
    
    @staticmethod
    def get_grouped_timezones():
        """Get timezones grouped by region for better UI organization"""
        timezones = TimezoneUtils.get_available_timezones()
        
        groups = {
            'UTC': [],
            'North America': [],
            'South America': [],
            'Europe': [],
            'Asia': [],
            'Australia & Oceania': [],
            'Africa': []
        }
        
        for tz in timezones:
            if tz == 'UTC':
                groups['UTC'].append(tz)
            elif tz.startswith('America/'):
                if tz in ['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 
                         'America/Phoenix', 'America/Anchorage', 'America/Honolulu', 'America/Toronto', 
                         'America/Vancouver', 'America/Mexico_City', 'America/Tijuana']:
                    groups['North America'].append(tz)
                else:
                    groups['South America'].append(tz)
            elif tz.startswith('Europe/'):
                groups['Europe'].append(tz)
            elif tz.startswith('Asia/'):
                groups['Asia'].append(tz)
            elif tz.startswith('Australia/') or tz.startswith('Pacific/'):
                groups['Australia & Oceania'].append(tz)
            elif tz.startswith('Africa/'):
                groups['Africa'].append(tz)
        
        return groups
    
    @staticmethod
    def format_timezone_display(tz_name):
        """Format timezone name for display with current offset"""
        try:
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            offset = now.strftime('%z')
            # Format offset as +/-HH:MM
            if len(offset) == 5:
                offset = offset[:3] + ':' + offset[3:]
            
            # Clean up timezone name for display
            display_name = tz_name.replace('_', ' ').replace('/', ' - ')
            
            return f"{display_name} (UTC{offset})"
        except:
            return tz_name
