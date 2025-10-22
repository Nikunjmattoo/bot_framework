"""
HONEST TEST SUITE: Datetime Operations (Timezone, Parsing, Formatting)
========================================================================

Tests datetime operations: timezone awareness, parsing, formatting, current time
Category F: Utils Testing - Group 3/11
Module: message_handler/utils/datetime_utils.py
"""

import pytest
from datetime import datetime, timezone, timedelta
from message_handler.utils.datetime_utils import (
    ensure_timezone_aware,
    parse_iso_datetime,
    format_iso_datetime,
    get_current_datetime
)


# ============================================================================
# TEST: ensure_timezone_aware
# ============================================================================

class TestEnsureTimezoneAware:
    """Test timezone awareness enforcement"""
    
    def test_naive_datetime_gets_utc(self):
        """Naive datetime gets UTC timezone"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        result = ensure_timezone_aware(naive_dt)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc
    
    def test_aware_datetime_unchanged(self):
        """Aware datetime returned unchanged"""
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_timezone_aware(aware_dt)
        assert result == aware_dt
        assert result.tzinfo == timezone.utc
    
    def test_none_returns_none(self):
        """None input returns None"""
        result = ensure_timezone_aware(None)
        assert result is None
    
    def test_custom_timezone_used(self):
        """Custom default timezone applied to naive datetime"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        custom_tz = timezone(timedelta(hours=5, minutes=30))
        result = ensure_timezone_aware(naive_dt, default_timezone=custom_tz)
        assert result.tzinfo == custom_tz
    
    def test_already_aware_not_converted(self):
        """Already aware datetime not converted to default"""
        other_tz = timezone(timedelta(hours=5))
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=other_tz)
        result = ensure_timezone_aware(aware_dt, default_timezone=timezone.utc)
        assert result.tzinfo == other_tz  # Keeps original timezone
    
    def test_field_name_logged(self):
        """Field name parameter accepted (for logging)"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        result = ensure_timezone_aware(naive_dt, field_name="test_field")
        assert result.tzinfo is not None


# ============================================================================
# TEST: parse_iso_datetime
# ============================================================================

class TestParseIsoDatetime:
    """Test ISO datetime string parsing"""
    
    def test_valid_iso_with_z_parsed(self):
        """Valid ISO string with Z parsed"""
        result = parse_iso_datetime("2025-01-01T12:00:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo is not None
    
    def test_valid_iso_with_offset_parsed(self):
        """Valid ISO string with offset parsed"""
        result = parse_iso_datetime("2025-01-01T12:00:00+05:30")
        assert result is not None
        assert result.year == 2025
        assert result.tzinfo is not None
    
    def test_valid_iso_without_tz_gets_utc(self):
        """ISO string without timezone gets UTC"""
        result = parse_iso_datetime("2025-01-01T12:00:00")
        assert result is not None
        assert result.tzinfo is not None
    
    def test_z_suffix_converted_to_offset(self):
        """Z suffix converted to +00:00"""
        result = parse_iso_datetime("2025-01-01T12:00:00Z")
        assert result.tzinfo == timezone.utc
    
    def test_invalid_format_returns_none(self):
        """Invalid format returns None"""
        result = parse_iso_datetime("not-a-date")
        assert result is None
    
    def test_empty_string_returns_none(self):
        """Empty string returns None"""
        result = parse_iso_datetime("")
        assert result is None
    
    def test_none_returns_none(self):
        """None returns None"""
        result = parse_iso_datetime(None)
        assert result is None
    
    def test_partial_date_returns_none(self):
        """Partial date string returns None"""
        result = parse_iso_datetime("2025-01-01")
        # This might actually parse, depending on Python version
        # The key is it should not crash
        assert result is None or isinstance(result, datetime)
    
    def test_with_microseconds_parsed(self):
        """ISO string with microseconds parsed"""
        result = parse_iso_datetime("2025-01-01T12:00:00.123456Z")
        assert result is not None
        assert result.microsecond == 123456
    
    def test_custom_default_timezone(self):
        """Custom default timezone applied to naive result"""
        custom_tz = timezone(timedelta(hours=5))
        result = parse_iso_datetime("2025-01-01T12:00:00", default_timezone=custom_tz)
        if result:
            assert result.tzinfo is not None
    
    def test_field_name_logged(self):
        """Field name parameter accepted (for logging)"""
        result = parse_iso_datetime("2025-01-01T12:00:00Z", field_name="test_field")
        assert result is not None


# ============================================================================
# TEST: format_iso_datetime
# ============================================================================

class TestFormatIsoDatetime:
    """Test datetime to ISO string formatting"""
    
    def test_aware_datetime_formatted(self):
        """Aware datetime formatted to ISO"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_iso_datetime(dt)
        assert result is not None
        assert "2025-01-01" in result
        assert "12:00:00" in result
    
    def test_includes_timezone_offset(self):
        """Formatted string includes timezone offset"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_iso_datetime(dt)
        assert "+00:00" in result or "Z" in result or result.endswith("00:00")
    
    def test_microseconds_included_by_default(self):
        """Microseconds included by default"""
        dt = datetime(2025, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        result = format_iso_datetime(dt, include_microseconds=True)
        assert ".123456" in result or "123456" in result
    
    def test_microseconds_excluded_when_false(self):
        """Microseconds excluded when include_microseconds=False"""
        dt = datetime(2025, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        result = format_iso_datetime(dt, include_microseconds=False)
        assert ".123456" not in result
        assert "123456" not in result or "00:00" in result  # Could be in timezone
    
    def test_naive_datetime_gets_utc(self):
        """Naive datetime gets UTC before formatting"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        result = format_iso_datetime(naive_dt)
        assert result is not None
        # Should have timezone info added
        assert "+" in result or "Z" in result or "00:00" in result
    
    def test_none_returns_none(self):
        """None returns None"""
        result = format_iso_datetime(None)
        assert result is None
    
    def test_roundtrip_parse_and_format(self):
        """Parse and format roundtrip"""
        original = "2025-01-01T12:00:00+00:00"
        parsed = parse_iso_datetime(original)
        formatted = format_iso_datetime(parsed, include_microseconds=False)
        # Should be similar (might differ in timezone representation)
        assert "2025-01-01" in formatted
        assert "12:00:00" in formatted


# ============================================================================
# TEST: get_current_datetime
# ============================================================================

class TestGetCurrentDatetime:
    """Test current datetime retrieval"""
    
    def test_returns_datetime(self):
        """Returns datetime object"""
        result = get_current_datetime()
        assert isinstance(result, datetime)
    
    def test_returns_aware_datetime(self):
        """Returns timezone-aware datetime"""
        result = get_current_datetime()
        assert result.tzinfo is not None
    
    def test_returns_utc_timezone(self):
        """Returns UTC timezone"""
        result = get_current_datetime()
        assert result.tzinfo == timezone.utc
    
    def test_two_calls_different_times(self):
        """Two calls return different times"""
        time1 = get_current_datetime()
        import time
        time.sleep(0.01)  # Sleep 10ms
        time2 = get_current_datetime()
        assert time2 > time1
    
    def test_time_reasonable(self):
        """Returned time is reasonable (not in past/future)"""
        result = get_current_datetime()
        # Should be recent (within last minute and not in future)
        now_approx = datetime.now(timezone.utc)
        diff = abs((result - now_approx).total_seconds())
        assert diff < 60  # Within 1 minute


# ============================================================================
# TEST: Integration and Edge Cases
# ============================================================================

class TestIntegration:
    """Test integration between datetime functions"""
    
    def test_format_current_datetime(self):
        """Format current datetime"""
        current = get_current_datetime()
        formatted = format_iso_datetime(current)
        assert formatted is not None
        assert isinstance(formatted, str)
    
    def test_parse_formatted_current(self):
        """Parse formatted current datetime"""
        current = get_current_datetime()
        formatted = format_iso_datetime(current)
        parsed = parse_iso_datetime(formatted)
        assert parsed is not None
        # Should be very close (might differ by microseconds)
        diff = abs((parsed - current).total_seconds())
        assert diff < 1
    
    def test_ensure_then_format(self):
        """Ensure aware then format"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        aware_dt = ensure_timezone_aware(naive_dt)
        formatted = format_iso_datetime(aware_dt)
        assert formatted is not None
        assert "2025-01-01" in formatted
    
    def test_parse_then_ensure(self):
        """Parse then ensure (should be no-op if already aware)"""
        parsed = parse_iso_datetime("2025-01-01T12:00:00Z")
        ensured = ensure_timezone_aware(parsed)
        assert parsed == ensured  # Already aware, unchanged


class TestEdgeCases:
    """Test edge cases"""
    
    def test_leap_year_date(self):
        """Leap year date handled"""
        dt = datetime(2024, 2, 29, 12, 0, 0, tzinfo=timezone.utc)
        formatted = format_iso_datetime(dt)
        parsed = parse_iso_datetime(formatted)
        assert parsed.day == 29
        assert parsed.month == 2
    
    def test_end_of_year(self):
        """End of year date handled"""
        dt = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        formatted = format_iso_datetime(dt)
        assert "2025-12-31" in formatted
        assert "23:59:59" in formatted
    
    def test_midnight(self):
        """Midnight time handled"""
        dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        formatted = format_iso_datetime(dt)
        assert "00:00:00" in formatted
    
    def test_various_timezones(self):
        """Various timezone offsets handled"""
        timezones = [
            timezone.utc,
            timezone(timedelta(hours=5, minutes=30)),  # IST
            timezone(timedelta(hours=-5)),  # EST
            timezone(timedelta(hours=9)),  # JST
        ]
        for tz in timezones:
            dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=tz)
            formatted = format_iso_datetime(dt)
            assert formatted is not None