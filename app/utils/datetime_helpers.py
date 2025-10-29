"""
DateTime helper utilities for safe timezone-aware datetime operations.

These helpers ensure safe comparisons between timezone-aware and potentially
naive datetimes loaded from the database.
"""
from datetime import datetime, timezone


def ensure_timezone_aware(dt: datetime, assume_utc: bool = True) -> datetime:
    """
    Ensure a datetime is timezone-aware.
    
    Args:
        dt: The datetime to check
        assume_utc: If True and datetime is naive, assume it's UTC (default: True)
        
    Returns:
        Timezone-aware datetime
        
    Example:
        >>> naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> aware_dt = ensure_timezone_aware(naive_dt)
        >>> aware_dt.tzinfo is not None
        True
    """
    if dt is None:
        return None
        
    if dt.tzinfo is None:
        # Naive datetime - add timezone
        if assume_utc:
            return dt.replace(tzinfo=timezone.utc)
        else:
            # Could use local timezone, but safer to be explicit
            raise ValueError("Naive datetime provided without explicit timezone handling")
    
    return dt


def safe_datetime_compare(dt1: datetime, dt2: datetime, assume_utc: bool = True) -> bool:
    """
    Safely compare two datetimes, handling timezone-aware and naive datetimes.
    
    Args:
        dt1: First datetime
        dt2: Second datetime
        assume_utc: If True, treat naive datetimes as UTC (default: True)
        
    Returns:
        True if dt1 > dt2
        
    Example:
        >>> now_aware = datetime.now(timezone.utc)
        >>> now_naive = datetime.utcnow()
        >>> safe_datetime_compare(now_aware, now_naive)  # No TypeError!
        False
    """
    if dt1 is None or dt2 is None:
        return False
        
    # Ensure both are timezone-aware
    dt1 = ensure_timezone_aware(dt1, assume_utc)
    dt2 = ensure_timezone_aware(dt2, assume_utc)
    
    return dt1 > dt2


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    This is the preferred way to get current time for database operations.
    
    Returns:
        Current UTC time with timezone info
        
    Example:
        >>> now = utc_now()
        >>> now.tzinfo is not None
        True
    """
    return datetime.now(timezone.utc)
