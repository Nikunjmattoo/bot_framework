"""
Datetime utilities for the message handler system.

This module provides utility functions for handling datetime objects
consistently across the message handler codebase.
"""
from datetime import datetime, timezone
from typing import Optional, Union
import logging

# Get package logger
logger = logging.getLogger("message_handler.utils.datetime")

def ensure_timezone_aware(
    dt: Optional[datetime],
    default_timezone: timezone = timezone.utc,
    field_name: Optional[str] = None
) -> Optional[datetime]:
    """
    Ensure a datetime object has timezone information.
    
    If the datetime is timezone-naive, it will be converted to the specified timezone.
    If the datetime is None, None will be returned.
    
    Args:
        dt: Datetime object to ensure has timezone info
        default_timezone: Timezone to use if dt is naive (default: UTC)
        field_name: Optional field name for logging context
        
    Returns:
        Timezone-aware datetime object or None
    """
    if dt is None:
        return None
        
    # Check if datetime is timezone-naive
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # Convert to the default timezone
        field_info = f" for {field_name}" if field_name else ""
        logger.debug(f"Converting naive datetime{field_info} to {default_timezone.tzname(None)}")
        return dt.replace(tzinfo=default_timezone)
        
    return dt

def parse_iso_datetime(
    date_string: Optional[str],
    default_timezone: timezone = timezone.utc,
    field_name: Optional[str] = None
) -> Optional[datetime]:
    """
    Parse an ISO format datetime string into a timezone-aware datetime object.
    
    Args:
        date_string: ISO format datetime string
        default_timezone: Timezone to use if string is naive (default: UTC)
        field_name: Optional field name for logging context
        
    Returns:
        Timezone-aware datetime object or None if parsing fails
    """
    if not date_string:
        return None
        
    try:
        # Try to parse with timezone information
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        # Ensure timezone is set
        return ensure_timezone_aware(dt, default_timezone, field_name)
    except (ValueError, AttributeError) as e:
        field_info = f" for {field_name}" if field_name else ""
        logger.warning(f"Failed to parse datetime string{field_info}: {date_string} - {str(e)}")
        return None

def format_iso_datetime(
    dt: Optional[datetime],
    include_microseconds: bool = True
) -> Optional[str]:
    """
    Format a datetime object as an ISO format string.
    
    Args:
        dt: Datetime object to format
        include_microseconds: Whether to include microseconds in the output
        
    Returns:
        ISO format datetime string or None if dt is None
    """
    if dt is None:
        return None
        
    # Ensure datetime is timezone-aware
    dt = ensure_timezone_aware(dt)
    
    # Format with or without microseconds
    if include_microseconds:
        return dt.isoformat()
    else:
        return dt.replace(microsecond=0).isoformat()

def get_current_datetime() -> datetime:
    """
    Get the current datetime with UTC timezone.
    
    Returns:
        Current timezone-aware datetime
    """
    return datetime.now(timezone.utc)

def is_recent(
    dt: Optional[datetime],
    minutes: int = 60,
    reference_time: Optional[datetime] = None
) -> bool:
    """
    Check if a datetime is recent compared to a reference time.
    
    Args:
        dt: Datetime to check
        minutes: Number of minutes to consider recent
        reference_time: Reference time to compare against (default: current time)
        
    Returns:
        True if dt is within the specified minutes of reference_time, False otherwise
    """
    if dt is None:
        return False
        
    # Ensure datetime is timezone-aware
    dt = ensure_timezone_aware(dt)
    
    # Get reference time
    if reference_time is None:
        reference_time = get_current_datetime()
    else:
        reference_time = ensure_timezone_aware(reference_time)
    
    # Calculate time difference in minutes
    diff = (reference_time - dt).total_seconds() / 60.0
    
    return 0 <= diff <= minutes

def update_session_timestamp(session, field_name="timestamp"):
    """
    Updates a session's timestamp to the current datetime.
    
    Args:
        session: The session object to update
        field_name: The name of the timestamp field (for error reporting)
        
    Returns:
        The updated session object
    """
    current_time = get_current_datetime()
    
    try:
        setattr(session, field_name, current_time)
    except AttributeError as e:
        raise ValueError(f"Failed to update {field_name} on session: {e}")
        
    return session