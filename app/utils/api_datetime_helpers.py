"""
API DateTime Response Helpers

These utilities ensure API responses clearly distinguish between:
- UTC storage format (what's in the database)
- User-localized display format (what the user sees)

Always include BOTH in API responses for clarity.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask_login import current_user


def format_datetime_for_api(dt: datetime, user_timezone: str = None) -> Dict[str, str]:
    """
    Format datetime for API response with BOTH UTC and user timezone.
    
    Args:
        dt: Datetime to format (should be timezone-aware UTC)
        user_timezone: Optional user timezone (defaults to current_user.timezone)
        
    Returns:
        Dictionary with both 'utc' and 'local' formatted times
        
    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2025, 10, 28, 14, 30, 0, tzinfo=timezone.utc)
        >>> format_datetime_for_api(dt, 'America/New_York')
        {
            'utc': '2025-10-28T14:30:00+00:00',
            'local': '2025-10-28T10:30:00-04:00',
            'display': 'Oct 28, 2025 10:30 AM EDT'
        }
    """
    if dt is None:
        return {'utc': None, 'local': None, 'display': None}
    
    from app.utils.timezone_utils import TimezoneUtils
    from app.utils.datetime_helpers import ensure_timezone_aware
    
    # Ensure datetime is timezone-aware
    dt = ensure_timezone_aware(dt)
    
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


def batch_datetime_response(batch) -> Dict[str, Any]:
    """
    Format batch timestamps for API response.
    
    STORAGE: All times stored in UTC (timezone-aware)
    DISPLAY: Converted to user's timezone
    
    Returns both UTC and localized times for client flexibility.
    """
    return {
        'id': batch.id,
        'status': batch.status,
        'started_at': format_datetime_for_api(batch.started_at),
        'completed_at': format_datetime_for_api(batch.completed_at) if batch.completed_at else None,
        'failed_at': format_datetime_for_api(batch.failed_at) if batch.failed_at else None,
        'cancelled_at': format_datetime_for_api(batch.cancelled_at) if batch.cancelled_at else None,
    }


def reservation_datetime_response(reservation) -> Dict[str, Any]:
    """
    Format reservation timestamps for API response.
    
    CRITICAL: Expiration times must be clear for POS integrations
    """
    from app.utils.datetime_helpers import ensure_timezone_aware
    
    return {
        'id': reservation.id,
        'order_id': reservation.order_id,
        'status': reservation.status,
        'created_at': format_datetime_for_api(reservation.created_at),
        'expires_at': format_datetime_for_api(reservation.expires_at) if reservation.expires_at else None,
        'released_at': format_datetime_for_api(reservation.released_at) if reservation.released_at else None,
        'converted_at': format_datetime_for_api(reservation.converted_at) if reservation.converted_at else None,
        'is_expired': reservation.is_expired,  # Calculated property (safe comparison)
    }


def inventory_history_response(entry) -> Dict[str, Any]:
    """
    Format inventory history entry for API response.
    
    STORAGE: timestamp in UTC
    DISPLAY: Converted to user's timezone
    """
    return {
        'id': entry.id,
        'timestamp': format_datetime_for_api(entry.timestamp),
        'change_type': entry.change_type,
        'quantity_change': entry.quantity_change,
        'unit': entry.unit,
        'expiration_date': format_datetime_for_api(entry.expiration_date) if entry.expiration_date else None,
    }
