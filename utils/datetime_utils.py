# utils/datetime_utils.py
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.tz import utc_tz

def utc_now() -> datetime:
    """
    Get current UTC time with timezone info.
    
    Returns:
        datetime: Current time in UTC with timezone
    """
    return datetime.now(utc_tz())

def ensure_tz_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime is timezone-aware by adding UTC if needed.
    
    Args:
        dt: Datetime to check
        
    Returns:
        Timezone-aware datetime or None if input was None
    """
    if dt is None:
        return None
        
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utc_tz())
        
    return dt

def is_expired(dt: Optional[datetime], max_age_minutes: int = 60) -> bool:
    """
    Check if a datetime is older than the specified age.
    
    Args:
        dt: Datetime to check
        max_age_minutes: Maximum age in minutes
        
    Returns:
        bool: True if expired, False if not or if dt is None
    """
    if dt is None:
        return False
        
    dt_aware = ensure_tz_aware(dt)
    age = utc_now() - dt_aware
    
    return age > timedelta(minutes=max_age_minutes)

def format_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Format a datetime as ISO 8601 string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        str: Formatted string or None if input was None
    """
    if dt is None:
        return None
        
    dt_aware = ensure_tz_aware(dt)
    return dt_aware.isoformat()