# utils/__init__.py
"""
Utility functions for the bot framework.
"""

# JSON utilities
from .json_utils import prepare_for_json, safe_parse_json, json_serialize

# Datetime utilities
from .datetime_utils import utc_now, ensure_tz_aware, format_iso, is_expired

# Timezone utilities
from .tz import utc_tz, get_tz

# Logging
from .logging import get_logger, log_json_to_file

# Telemetry
from .telemetry import log_event, perf_timer, stage_timer, stage_start, stage_end

__all__ = [
    # JSON
    "prepare_for_json",
    "safe_parse_json",
    "json_serialize",
    
    # Datetime
    "utc_now",
    "ensure_tz_aware",
    "format_iso",
    "is_expired",
    
    # Timezone
    "utc_tz",
    "get_tz",
    
    # Logging
    "get_logger",
    "log_json_to_file",
    
    # Telemetry
    "log_event",
    "perf_timer",
    "stage_timer",
    "stage_start",
    "stage_end"
]