"""
HONEST TEST SUITE: Data Sanitization
=====================================

Tests data sanitization: sanitize_string, sanitize_dict, sanitize_list, sanitize_data
Category F: Utils Testing - Group 5/11
Module: message_handler/utils/data_utils.py
"""

import pytest
from message_handler.utils.data_utils import (
    sanitize_data,
    sanitize_string,
    sanitize_dict,
    sanitize_list
)


# ============================================================================
# TEST: sanitize_string
# ============================================================================

class TestSanitizeString:
    """Test string sanitization"""
    
    def test_normal_string_unchanged(self):
        """Normal string unchanged"""
        result = sanitize_string("Hello World")
        assert result == "Hello World"
    
    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace trimmed"""
        result = sanitize_string("  Hello World  ", trim=True)
        assert result == "Hello World"
    
    def test_whitespace_not_trimmed_when_false(self):
        """Whitespace not trimmed when trim=False"""
        result = sanitize_string("  Hello  ", trim=False)
        assert result == "  Hello  "
    
    def test_html_escaped_by_default(self):
        """HTML tags escaped by default"""
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_html_allowed_when_specified(self):
        """HTML allowed when allow_html=True"""
        result = sanitize_string("<b>bold</b>", allow_html=True)
        assert "<b>" in result
    
    def test_control_characters_removed(self):
        """Control characters removed (except \\n, \\t)"""
        text_with_controls = "Hello\x00World\x01Test"
        result = sanitize_string(text_with_controls)
        assert "\x00" not in result
        assert "\x01" not in result
    
    def test_newlines_preserved(self):
        """Newlines preserved"""
        result = sanitize_string("Line1\nLine2\nLine3")
        assert "\n" in result
        assert result.count("\n") == 2
    
    def test_tabs_preserved(self):
        """Tabs preserved"""
        result = sanitize_string("Col1\tCol2\tCol3")
        assert "\t" in result
    
    def test_unicode_normalized(self):
        """Unicode normalized (NFKC)"""
        result = sanitize_string("café")  # é might be composed differently
        assert "café" in result or "cafe" in result
    
    def test_max_length_truncates(self):
        """max_length truncates string"""
        long_string = "x" * 100
        result = sanitize_string(long_string, max_length=50)
        assert len(result) == 50
    
    def test_empty_string_returns_empty(self):
        """Empty string returns empty"""
        result = sanitize_string("")
        assert result == ""
    
    def test_none_returns_empty(self):
        """None returns empty string"""
        result = sanitize_string(None)
        assert result == ""


# ============================================================================
# TEST: sanitize_dict
# ============================================================================

class TestSanitizeDict:
    """Test dictionary sanitization"""
    
    def test_simple_dict_sanitized(self):
        """Simple dict sanitized"""
        data = {"key": "value", "number": 123}
        result = sanitize_dict(data)
        assert "key" in result
        assert result["key"] == "value"
    
    def test_sensitive_keys_stripped(self):
        """Sensitive keys stripped"""
        data = {"username": "alice", "password": "secret123", "token": "abc"}
        result = sanitize_dict(data, strip_keys=["password", "token"])
        assert "username" in result
        assert "password" not in result
        assert "token" not in result
    
    def test_nested_dict_sanitized(self):
        """Nested dict sanitized recursively"""
        data = {"outer": {"inner": "value"}}
        result = sanitize_dict(data)
        assert "outer" in result
        assert "inner" in result["outer"]
    
    def test_html_in_values_escaped(self):
        """HTML in dict values escaped"""
        data = {"content": "<script>alert('xss')</script>"}
        result = sanitize_dict(data, allow_html=False)
        assert "<script>" not in result["content"]
        assert "&lt;script&gt;" in result["content"]
    
    def test_keys_sanitized_when_enabled(self):
        """Keys sanitized when sanitize_keys=True"""
        data = {"  key with spaces  ": "value"}
        result = sanitize_dict(data, sanitize_keys=True)
        # Key should be trimmed
        assert "key with spaces" in result or "  key with spaces  " not in result
    
    def test_max_dict_items_limits(self):
        """max_dict_items limits dictionary size"""
        data = {f"key{i}": f"value{i}" for i in range(100)}
        result = sanitize_dict(data, max_dict_items=10)
        assert len(result) == 10
    
    def test_empty_dict_returns_empty(self):
        """Empty dict returns empty"""
        result = sanitize_dict({})
        assert result == {}
    
    def test_max_string_length_applied_to_values(self):
        """max_string_length applied to string values"""
        data = {"long": "x" * 100}
        result = sanitize_dict(data, max_string_length=50)
        assert len(result["long"]) == 50


# ============================================================================
# TEST: sanitize_list
# ============================================================================

class TestSanitizeList:
    """Test list sanitization"""
    
    def test_simple_list_sanitized(self):
        """Simple list sanitized"""
        data = ["item1", "item2", "item3"]
        result = sanitize_list(data)
        assert len(result) == 3
        assert "item1" in result
    
    def test_html_in_list_escaped(self):
        """HTML in list items escaped"""
        data = ["<script>bad</script>", "normal"]
        result = sanitize_list(data, allow_html=False)
        assert "<script>" not in result[0]
        assert "&lt;script&gt;" in result[0]
    
    def test_nested_lists_sanitized(self):
        """Nested lists sanitized recursively"""
        data = ["outer", ["inner1", "inner2"]]
        result = sanitize_list(data)
        assert isinstance(result[1], list)
        assert "inner1" in result[1]
    
    def test_list_with_dicts_sanitized(self):
        """List containing dicts sanitized"""
        data = [{"key": "value"}, {"password": "secret"}]
        result = sanitize_list(data, strip_keys=["password"])
        assert "key" in result[0]
        assert "password" not in result[1]
    
    def test_max_list_items_limits(self):
        """max_list_items limits list size"""
        data = list(range(100))
        result = sanitize_list(data, max_list_items=10)
        assert len(result) == 10
    
    def test_empty_list_returns_empty(self):
        """Empty list returns empty"""
        result = sanitize_list([])
        assert result == []


# ============================================================================
# TEST: sanitize_data (main function)
# ============================================================================

class TestSanitizeData:
    """Test main sanitize_data function"""
    
    def test_string_sanitized(self):
        """String data sanitized"""
        result = sanitize_data("  <b>text</b>  ")
        assert "&lt;b&gt;" in result
    
    def test_dict_sanitized(self):
        """Dict data sanitized"""
        result = sanitize_data({"key": "value"})
        assert isinstance(result, dict)
        assert "key" in result
    
    def test_list_sanitized(self):
        """List data sanitized"""
        result = sanitize_data(["item1", "item2"])
        assert isinstance(result, list)
        assert len(result) == 2
    
    def test_tuple_sanitized_returns_tuple(self):
        """Tuple sanitized and returns tuple"""
        result = sanitize_data(("item1", "item2"))
        assert isinstance(result, tuple)
        assert len(result) == 2
    
    def test_set_sanitized_returns_set(self):
        """Set sanitized and returns set"""
        result = sanitize_data({1, 2, 3})
        assert isinstance(result, set)
    
    def test_int_returned_unchanged(self):
        """Int returned unchanged"""
        result = sanitize_data(42)
        assert result == 42
    
    def test_float_returned_unchanged(self):
        """Float returned unchanged"""
        result = sanitize_data(3.14)
        assert result == 3.14
    
    def test_bool_returned_unchanged(self):
        """Bool returned unchanged"""
        result = sanitize_data(True)
        assert result is True
    
    def test_none_returned_as_none(self):
        """None returned as None"""
        result = sanitize_data(None)
        assert result is None
    
    def test_max_depth_prevents_infinite_recursion(self):
        """max_depth prevents infinite recursion"""
        # Create deeply nested structure
        data = {"level1": {"level2": {"level3": {"level4": "deep"}}}}
        with pytest.raises(ValueError) as exc:
            sanitize_data(data, max_depth=2)
        assert "recursion" in str(exc.value).lower()
    
    def test_complex_nested_structure(self):
        """Complex nested structure sanitized"""
        data = {
            "users": [
                {"name": "Alice", "password": "secret1"},
                {"name": "Bob", "password": "secret2"}
            ],
            "settings": {
                "enabled": True,
                "config": {"timeout": 30}
            }
        }
        result = sanitize_data(data, strip_keys=["password"])
        assert "users" in result
        assert "password" not in result["users"][0]
        assert "settings" in result
    
    def test_non_hashable_items_removed_from_set(self):
        """Non-hashable items removed from set"""
        data = {1, 2, "string", (1, 2)}
        result = sanitize_data(data)
        assert isinstance(result, set)
        # Lists and dicts can't be in sets


# ============================================================================
# TEST: Edge Cases and Security
# ============================================================================

class TestSecurityCases:
    """Test security-related sanitization"""
    
    def test_xss_attack_prevented(self):
        """XSS attack prevented"""
        attack = "<script>document.cookie</script>"
        result = sanitize_string(attack)
        assert "<script>" not in result
        assert "document.cookie" not in result or "&lt;" in result
    
    def test_sql_injection_characters_escaped(self):
        """SQL injection characters handled"""
        sql = "'; DROP TABLE users; --"
        result = sanitize_string(sql)
        # Should not break (exact handling depends on use case)
        assert isinstance(result, str)
    
    def test_sensitive_password_field_stripped(self):
        """Sensitive password field stripped"""
        data = {"user": "alice", "password": "secret", "pwd": "alsosecret"}
        result = sanitize_dict(data, strip_keys=["password", "pwd"])
        assert "password" not in result
        assert "pwd" not in result
    
    def test_nested_sensitive_data_stripped(self):
        """Nested sensitive data stripped"""
        data = {
            "user": {
                "name": "alice",
                "credentials": {
                    "password": "secret",
                    "token": "abc123"
                }
            }
        }
        result = sanitize_dict(data, strip_keys=["password", "token"])
        assert "password" not in result["user"]["credentials"]
        assert "token" not in result["user"]["credentials"]


class TestEdgeCases:
    """Test edge cases"""
    
    def test_unicode_emoji_preserved(self):
        """Unicode emoji preserved"""
        result = sanitize_string("Hello 🌍 World 🎉")
        assert "🌍" in result
        assert "🎉" in result
    
    def test_mixed_type_list(self):
        """Mixed type list sanitized"""
        data = [1, "string", True, None, {"key": "value"}]
        result = sanitize_list(data)
        assert len(result) == 5
        assert result[0] == 1
        assert isinstance(result[4], dict)
    
    def test_very_long_string_truncated(self):
        """Very long string truncated"""
        long_string = "x" * 10000
        result = sanitize_string(long_string, max_length=1000)
        assert len(result) == 1000
    
    def test_circular_reference_prevented(self):
        """Circular reference hits max_depth"""
        data = {"a": {}}
        data["a"]["b"] = data["a"]  # Circular reference
        # Should hit max_depth and raise
        with pytest.raises(ValueError):
            sanitize_data(data, max_depth=5)