"""
FILE: test/utils/test_telemetry.py
===================================
"""

import pytest
import time
import threading
from utils.telemetry import (
    log_event,
    perf_timer,
    recent_events,
    clear_events,
    stage_start,
    stage_end,
    stage_timer,
    _now_ms
)


# ============================================================================
# TEST: log_event
# ============================================================================

class TestLogEvent:
    """Test event logging"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_logs_event_with_kind_and_name(self):
        """Logs event with kind and name"""
        log_event("TEST", "test_event")
        events = recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["kind"] == "TEST"
        assert events[0]["name"] == "test_event"
    
    def test_logs_event_with_data(self):
        """Logs event with data"""
        log_event("TEST", "test_event", {"key": "value", "number": 42})
        events = recent_events(limit=1)
        assert events[0]["key"] == "value"
        assert events[0]["number"] == 42
    
    def test_logs_event_with_none_data(self):
        """Logs event with None data"""
        log_event("TEST", "test_event", None)
        events = recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["kind"] == "TEST"
    
    def test_event_includes_timestamp(self):
        """Event includes timestamp"""
        before = _now_ms()
        log_event("TEST", "test_event")
        after = _now_ms()
        
        events = recent_events(limit=1)
        assert "ts_ms" in events[0]
        assert before <= events[0]["ts_ms"] <= after
    
    def test_event_includes_trace_id_from_data(self):
        """Event includes trace_id from data"""
        log_event("TEST", "test_event", {"trace_id": "trace123"})
        events = recent_events(limit=1)
        assert events[0]["trace_id"] == "trace123"
    
    def test_event_trace_id_none_if_not_provided(self):
        """Event trace_id is None if not provided"""
        log_event("TEST", "test_event", {"other": "data"})
        events = recent_events(limit=1)
        assert events[0].get("trace_id") is None
    
    def test_event_with_level(self):
        """Event includes level"""
        log_event("TEST", "test_event", level="error")
        events = recent_events(limit=1)
        assert events[0]["level"] == "error"
    
    def test_event_default_level_info(self):
        """Event default level is info"""
        log_event("TEST", "test_event")
        events = recent_events(limit=1)
        assert events[0]["level"] == "info"
    
    def test_event_with_warning_level(self):
        """Event with warning level"""
        log_event("TEST", "test_event", level="warning")
        events = recent_events(limit=1)
        assert events[0]["level"] == "warning"
    
    def test_multiple_events_logged(self):
        """Multiple events logged in order"""
        log_event("TEST", "event1")
        log_event("TEST", "event2")
        log_event("TEST", "event3")
        
        events = recent_events(limit=10)
        names = [e["name"] for e in events]
        assert names == ["event3", "event2", "event1"]  # Most recent first
    
    def test_event_with_complex_data(self):
        """Event with complex nested data"""
        data = {
            "user": {"id": "user123", "role": "admin"},
            "metadata": {"count": 5}
        }
        log_event("TEST", "complex", data)
        events = recent_events(limit=1)
        assert events[0]["user"]["id"] == "user123"


# ============================================================================
# TEST: perf_timer
# ============================================================================

class TestPerfTimer:
    """Test performance timer"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_timer_logs_start_event(self):
        """Timer logs start event"""
        with perf_timer("PERF", "test_op"):
            pass
        
        events = recent_events(limit=10)
        start_events = [e for e in events if e["name"] == "test_op:start"]
        assert len(start_events) == 1
    
    def test_timer_logs_end_event(self):
        """Timer logs end event"""
        with perf_timer("PERF", "test_op"):
            pass
        
        events = recent_events(limit=10)
        end_events = [e for e in events if e["name"] == "test_op:end"]
        assert len(end_events) == 1
    
    def test_timer_measures_duration(self):
        """Timer measures duration in milliseconds"""
        with perf_timer("PERF", "test_op"):
            time.sleep(0.05)  # 50ms
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "test_op:end"][0]
        
        assert "latency_ms" in end_event
        assert end_event["latency_ms"] >= 40  # At least 40ms (accounting for variance)
        assert end_event["latency_ms"] < 200  # Not too long
    
    def test_timer_includes_kind(self):
        """Timer includes kind in events"""
        with perf_timer("CUSTOM", "test_op"):
            pass
        
        events = recent_events(limit=10)
        assert all(e["kind"] == "CUSTOM" for e in events)
    
    def test_timer_with_data(self):
        """Timer includes provided data"""
        with perf_timer("PERF", "test_op", {"user_id": "user123"}):
            pass
        
        events = recent_events(limit=10)
        assert events[0]["user_id"] == "user123"
        assert events[1]["user_id"] == "user123"
    
    def test_timer_logs_error_on_exception(self):
        """Timer logs error when exception raised"""
        try:
            with perf_timer("PERF", "failing_op"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "failing_op:end"][0]
        
        assert "error" in end_event
        assert "ValueError" in end_event["error"]
        assert end_event["level"] == "error"
    
    def test_timer_still_measures_duration_on_error(self):
        """Timer measures duration even when exception raised"""
        try:
            with perf_timer("PERF", "failing_op"):
                time.sleep(0.05)
                raise ValueError("Test error")
        except ValueError:
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "failing_op:end"][0]
        
        assert "latency_ms" in end_event
        assert end_event["latency_ms"] >= 40
    
    def test_timer_default_level_info(self):
        """Timer default level is info"""
        with perf_timer("PERF", "test_op"):
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "test_op:end"][0]
        assert end_event["level"] == "info"
    
    def test_timer_custom_level(self):
        """Timer respects custom level"""
        with perf_timer("PERF", "test_op", level="debug"):
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "test_op:end"][0]
        assert end_event["level"] == "debug"
    
    def test_nested_timers(self):
        """Nested timers work correctly"""
        with perf_timer("PERF", "outer"):
            time.sleep(0.01)
            with perf_timer("PERF", "inner"):
                time.sleep(0.01)
        
        events = recent_events(limit=10)
        outer_end = [e for e in events if e["name"] == "outer:end"][0]
        inner_end = [e for e in events if e["name"] == "inner:end"][0]
        
        assert outer_end["latency_ms"] > inner_end["latency_ms"]
    
    def test_timer_with_none_data(self):
        """Timer with None data works"""
        with perf_timer("PERF", "test_op", None):
            pass
        
        events = recent_events(limit=10)
        assert len(events) == 2  # start and end


# ============================================================================
# TEST: recent_events
# ============================================================================

class TestRecentEvents:
    """Test event retrieval"""
    
    def setup_method(self):
        """Clear and populate events"""
        clear_events()
        log_event("TYPE1", "event1", {"value": 1})
        time.sleep(0.01)
        log_event("TYPE2", "event2", {"value": 2})
        time.sleep(0.01)
        log_event("TYPE1", "event3", {"value": 3})
    
    def test_returns_all_events(self):
        """Returns all events when limit is high"""
        events = recent_events(limit=100)
        assert len(events) == 3
    
    def test_returns_in_reverse_chronological_order(self):
        """Returns events in reverse chronological order (most recent first)"""
        events = recent_events(limit=10)
        values = [e["value"] for e in events]
        assert values == [3, 2, 1]
    
    def test_limit_parameter_works(self):
        """Limit parameter restricts number of results"""
        events = recent_events(limit=2)
        assert len(events) == 2
        values = [e["value"] for e in events]
        assert values == [3, 2]
    
    def test_limit_one(self):
        """Limit of 1 returns only most recent"""
        events = recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["value"] == 3
    
    def test_filter_by_single_kind(self):
        """Filter by single kind"""
        events = recent_events(kinds=["TYPE1"])
        assert len(events) == 2
        assert all(e["kind"] == "TYPE1" for e in events)
    
    def test_filter_by_multiple_kinds(self):
        """Filter by multiple kinds"""
        events = recent_events(kinds=["TYPE1", "TYPE2"])
        assert len(events) == 3
    
    def test_filter_by_single_name(self):
        """Filter by single name"""
        events = recent_events(names=["event1"])
        assert len(events) == 1
        assert events[0]["name"] == "event1"
    
    def test_filter_by_multiple_names(self):
        """Filter by multiple names"""
        events = recent_events(names=["event1", "event3"])
        assert len(events) == 2
        names = [e["name"] for e in events]
        assert set(names) == {"event1", "event3"}
    
    def test_filter_by_kind_and_name(self):
        """Filter by both kind and name"""
        events = recent_events(kinds=["TYPE1"], names=["event3"])
        assert len(events) == 1
        assert events[0]["kind"] == "TYPE1"
        assert events[0]["name"] == "event3"
    
    def test_filter_by_timestamp(self):
        """Filter by timestamp"""
        clear_events()
        log_event("TEST", "old_event")
        time.sleep(0.02)
        cutoff = _now_ms()
        time.sleep(0.02)
        log_event("TEST", "new_event")
        
        events = recent_events(since_ts_ms=cutoff)
        assert len(events) == 1
        assert events[0]["name"] == "new_event"
    
    def test_combined_filters(self):
        """Combined filters work together"""
        clear_events()
        log_event("TYPE1", "event_a")
        time.sleep(0.01)
        cutoff = _now_ms()
        time.sleep(0.01)
        log_event("TYPE1", "event_b")
        log_event("TYPE2", "event_c")
        
        events = recent_events(
            kinds=["TYPE1"],
            names=["event_b"],
            since_ts_ms=cutoff,
            limit=10
        )
        assert len(events) == 1
        assert events[0]["name"] == "event_b"
    
    def test_no_events_returns_empty_list(self):
        """No events returns empty list"""
        clear_events()
        events = recent_events(limit=10)
        assert events == []
    
    def test_filter_no_matches_returns_empty(self):
        """Filter with no matches returns empty list"""
        events = recent_events(kinds=["NONEXISTENT"])
        assert events == []


# ============================================================================
# TEST: clear_events
# ============================================================================

class TestClearEvents:
    """Test event clearing"""
    
    def test_clears_all_events(self):
        """Clears all events from buffer (FIXED)"""
        clear_events()  # Ensure clean start
        
        log_event("TEST", "event1")
        log_event("TEST", "event2")
        log_event("TEST", "event3")
        
        assert len(recent_events(limit=10)) == 3
        
        clear_events()
        
        assert len(recent_events(limit=10)) == 0
    
    def test_can_log_after_clear(self):
        """Can log new events after clearing"""
        log_event("TEST", "before_clear")
        clear_events()
        log_event("TEST", "after_clear")
        
        events = recent_events(limit=10)
        assert len(events) == 1
        assert events[0]["name"] == "after_clear"
    
    def test_multiple_clears(self):
        """Multiple clears work"""
        log_event("TEST", "event1")
        clear_events()
        clear_events()
        
        assert len(recent_events(limit=10)) == 0

    def setup_method(self):
        """Clear events before each test"""
        clear_events()


# ============================================================================
# TEST: stage_start
# ============================================================================

class TestStageStart:
    """Test stage start logging"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_logs_stage_start_event(self):
        """Logs stage start event"""
        stage_start("trace123", "processing")
        
        events = recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["kind"] == "STAGE"
        assert events[0]["name"] == "processing:start"
    
    def test_includes_trace_id(self):
        """Includes trace_id in event"""
        stage_start("trace456", "validation")
        
        events = recent_events(limit=1)
        assert events[0]["trace_id"] == "trace456"
    
    def test_includes_metadata(self):
        """Includes metadata if provided"""
        stage_start("trace789", "processing", {"user_id": "user123"})
        
        events = recent_events(limit=1)
        assert events[0]["user_id"] == "user123"
    
    def test_none_metadata(self):
        """None metadata works"""
        stage_start("trace000", "processing", None)
        
        events = recent_events(limit=1)
        assert events[0]["trace_id"] == "trace000"


# ============================================================================
# TEST: stage_end
# ============================================================================

class TestStageEnd:
    """Test stage end logging"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_logs_stage_end_event(self):
        """Logs stage end event"""
        stage_end("trace123", "processing")
        
        events = recent_events(limit=1)
        assert events[0]["kind"] == "STAGE"
        assert events[0]["name"] == "processing:end"
    
    def test_includes_ok_status_true(self):
        """Includes ok=True for success"""
        stage_end("trace123", "processing", ok=True)
        
        events = recent_events(limit=1)
        assert events[0]["ok"] is True
    
    def test_includes_ok_status_false(self):
        """Includes ok=False for failure"""
        stage_end("trace123", "processing", ok=False)
        
        events = recent_events(limit=1)
        assert events[0]["ok"] is False
    
    def test_default_ok_is_true(self):
        """Default ok status is True"""
        stage_end("trace123", "processing")
        
        events = recent_events(limit=1)
        assert events[0]["ok"] is True
    
    def test_includes_error_message(self):
        """Includes error message if provided"""
        stage_end("trace123", "processing", ok=False, error="Validation failed")
        
        events = recent_events(limit=1)
        assert events[0]["error"] == "Validation failed"
    
    def test_level_error_when_not_ok(self):
        """Level is error when ok=False"""
        stage_end("trace123", "processing", ok=False)
        
        events = recent_events(limit=1)
        assert events[0]["level"] == "error"
    
    def test_level_info_when_ok(self):
        """Level is info when ok=True"""
        stage_end("trace123", "processing", ok=True)
        
        events = recent_events(limit=1)
        assert events[0]["level"] == "info"
    
    def test_includes_metadata(self):
        """Includes metadata if provided"""
        stage_end("trace123", "processing", meta={"duration_s": 1.5})
        
        events = recent_events(limit=1)
        assert events[0]["duration_s"] == 1.5


# ============================================================================
# TEST: stage_timer
# ============================================================================

class TestStageTimer:
    """Test stage timer context manager"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_logs_stage_start_and_end(self):
        """Logs both stage start and end events"""
        with stage_timer("trace123", "processing"):
            pass
        
        events = recent_events(limit=10)
        names = [e["name"] for e in events]
        
        assert "processing:start" in names
        assert "processing:end" in names
    
    def test_end_event_ok_true_on_success(self):
        """End event has ok=True on success"""
        with stage_timer("trace123", "processing"):
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "processing:end"][0]
        
        assert end_event["ok"] is True
    
    def test_end_event_ok_false_on_exception(self):
        """End event has ok=False on exception"""
        try:
            with stage_timer("trace123", "failing"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "failing:end"][0]
        
        assert end_event["ok"] is False
    
    def test_includes_error_message_on_exception(self):
        """Includes error message on exception"""
        try:
            with stage_timer("trace123", "failing"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        events = recent_events(limit=10)
        end_event = [e for e in events if e["name"] == "failing:end"][0]
        
        assert "error" in end_event
        assert "ValueError" in end_event["error"]
    
    def test_includes_metadata(self):
        """Includes metadata in both events"""
        with stage_timer("trace123", "processing", {"user_id": "user123"}):
            pass
        
        events = recent_events(limit=10)
        
        assert all(e["user_id"] == "user123" for e in events)
    
    def test_nested_stage_timers(self):
        """Nested stage timers work"""
        with stage_timer("trace123", "outer"):
            with stage_timer("trace123", "inner"):
                pass
        
        events = recent_events(limit=10)
        names = [e["name"] for e in events]
        
        assert "outer:start" in names
        assert "inner:start" in names
        assert "inner:end" in names
        assert "outer:end" in names


# ============================================================================
# TEST: Thread Safety
# ============================================================================

class TestThreadSafety:
    """Test thread safety of telemetry"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_concurrent_logging(self):
        """Concurrent logging from multiple threads"""
        def log_events(thread_id):
            for i in range(10):
                log_event("TEST", f"event_{thread_id}_{i}", {"thread": thread_id})
        
        threads = [threading.Thread(target=log_events, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        events = recent_events(limit=100)
        assert len(events) == 50  # 5 threads * 10 events
    
    def test_concurrent_clearing(self):
        """Concurrent clearing and logging"""
        def log_and_clear():
            for _ in range(10):
                log_event("TEST", "event")
                clear_events()
        
        threads = [threading.Thread(target=log_and_clear) for _ in range(3)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not crash


# ============================================================================
# TEST: Buffer Limits
# ============================================================================

class TestBufferLimits:
    """Test event buffer limits"""
    
    def setup_method(self):
        """Clear events before each test"""
        clear_events()
    
    def test_buffer_max_size(self):
        """Buffer respects max size"""
        # Log more than max events
        for i in range(6000):
            log_event("TEST", f"event_{i}")
        
        events = recent_events(limit=10000)
        # Should be capped at _MAX_EVENTS (5000)
        assert len(events) <= 5000
    
    def test_oldest_events_dropped(self):
        """Oldest events dropped when buffer full"""
        for i in range(6000):
            log_event("TEST", f"event_{i}", {"index": i})
        
        events = recent_events(limit=10000)
        # Should have newest events
        indices = [e["index"] for e in events]
        assert max(indices) == 5999
        assert min(indices) >= 1000  # Old ones dropped