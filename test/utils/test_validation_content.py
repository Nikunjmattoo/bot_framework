"""
HONEST TEST SUITE: Content Validation (Length, Metadata Size)
==============================================================

Tests content-specific validation: message length, metadata size
Category F: Utils Testing - Group 2/11
Module: message_handler/utils/validation.py
"""

import pytest
import json
from message_handler.utils.validation import (
    validate_content_length,
    validate_metadata_field_size,
    MAX_MESSAGE_LENGTH
)
from message_handler.exceptions import ValidationError, ErrorCode


# ============================================================================
# TEST: validate_content_length
# ============================================================================

class TestValidateContentLength:
    """Test message content length validation"""
    
    def test_content_within_limit_passes(self):
        """Content within limit passes"""
        content = "Hello world" * 100
        is_valid, error, normalized = validate_content_length(content)
        assert is_valid is True
        assert error is None
        assert normalized == content.strip()
    
    def test_content_exceeds_limit_fails(self):
        """Content > MAX_MESSAGE_LENGTH fails"""
        long_content = "x" * (MAX_MESSAGE_LENGTH + 1)
        is_valid, error, _ = validate_content_length(long_content)
        assert is_valid is False
        assert error is not None
        assert "exceeds maximum length" in error.lower() or "maximum" in error.lower()
    
    def test_content_exactly_at_limit_passes(self):
        """Content exactly at MAX_MESSAGE_LENGTH passes"""
        content = "x" * MAX_MESSAGE_LENGTH
        is_valid, error, normalized = validate_content_length(content)
        assert is_valid is True
        assert error is None
    
    def test_empty_content_allowed(self):
        """Empty content allowed (not required by default)"""
        is_valid, error, normalized = validate_content_length("")
        assert is_valid is True
        assert normalized == ""
    
    def test_content_trimmed(self):
        """Content whitespace trimmed"""
        content = "  hello world  "
        is_valid, error, normalized = validate_content_length(content)
        assert normalized == "hello world"
    
    def test_custom_max_length_respected(self):
        """Custom max_length parameter respected"""
        content = "x" * 100
        is_valid, error, _ = validate_content_length(content, max_length=50)
        assert is_valid is False
    
    def test_raise_error_flag_raises(self):
        """raise_error=True raises ValidationError"""
        long_content = "x" * (MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(ValidationError) as exc:
            validate_content_length(long_content, raise_error=True)
        assert exc.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_error_includes_length_details(self):
        """ValidationError includes length details"""
        long_content = "x" * (MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(ValidationError) as exc:
            validate_content_length(long_content, raise_error=True)
        assert hasattr(exc.value, 'details')
        if exc.value.details:
            assert 'length' in exc.value.details or 'max_length' in exc.value.details
    
    def test_custom_field_name(self):
        """Custom field_name in error message"""
        long_content = "x" * (MAX_MESSAGE_LENGTH + 1)
        is_valid, error, _ = validate_content_length(long_content, field_name="description")
        assert "description" in error.lower()
    
    def test_none_content_treated_as_empty(self):
        """None content treated as empty string"""
        is_valid, error, normalized = validate_content_length(None)
        assert is_valid is True
        assert normalized == ""


# ============================================================================
# TEST: validate_metadata_field_size
# ============================================================================

class TestValidateMetadataFieldSize:
    """Test metadata size validation"""
    
    def test_small_metadata_passes(self):
        """Small metadata passes"""
        metadata = {"key": "value", "number": 123, "list": [1, 2, 3]}
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert error is None
        assert normalized == metadata
    
    def test_empty_metadata_passes(self):
        """Empty dict passes"""
        is_valid, error, normalized = validate_metadata_field_size({})
        assert is_valid is True
        assert normalized == {}
    
    def test_none_metadata_passes(self):
        """None returns empty dict"""
        is_valid, error, normalized = validate_metadata_field_size(None)
        assert is_valid is True
        assert normalized == {}
    
    def test_non_dict_metadata_fails(self):
        """Non-dict metadata fails"""
        is_valid, error, normalized = validate_metadata_field_size("not a dict")
        assert is_valid is False
        assert error is not None
        assert "must be a dictionary" in error.lower()
    
    def test_list_metadata_fails(self):
        """List metadata fails"""
        is_valid, error, _ = validate_metadata_field_size([1, 2, 3])
        assert is_valid is False
        assert "must be a dictionary" in error.lower()
    
    def test_large_metadata_fails(self):
        """Metadata > max_size_kb fails"""
        large_metadata = {"data": "x" * (70 * 1024)}  # 70KB
        is_valid, error, normalized = validate_metadata_field_size(large_metadata, max_size_kb=64)
        assert is_valid is False
        assert error is not None
        assert "exceeds maximum size" in error.lower()
    
    def test_truncated_metadata_returned(self):
        """Truncated metadata returned on failure"""
        large_metadata = {"data": "x" * (70 * 1024)}
        is_valid, error, normalized = validate_metadata_field_size(large_metadata, max_size_kb=64)
        assert is_valid is False
        assert "truncated" in normalized
        assert normalized["truncated"] is True
    
    def test_metadata_at_limit_passes(self):
        """Metadata at size limit passes"""
        metadata = {"data": "x" * (60 * 1024)}  # Just under 64KB
        is_valid, error, normalized = validate_metadata_field_size(metadata, max_size_kb=64)
        assert is_valid is True
    
    def test_essential_fields_preserved_on_truncation(self):
        """Essential fields preserved when truncated"""
        large_metadata = {
            "channel": "whatsapp",
            "message_type": "text",
            "timestamp": "2025-01-01T00:00:00Z",
            "source": "user",
            "large_data": "x" * (70 * 1024)
        }
        is_valid, error, normalized = validate_metadata_field_size(large_metadata, max_size_kb=64)
        assert is_valid is False
        # Check essential fields preserved
        assert "channel" in normalized
        assert normalized["channel"] == "whatsapp"
        assert "message_type" in normalized
        assert "timestamp" in normalized
        assert "source" in normalized
    
    def test_non_essential_field_not_preserved(self):
        """Non-essential fields dropped on truncation"""
        large_metadata = {
            "channel": "whatsapp",
            "random_field": "x" * (70 * 1024)
        }
        is_valid, error, normalized = validate_metadata_field_size(large_metadata, max_size_kb=64)
        assert "random_field" not in normalized or len(str(normalized.get("random_field", ""))) < 1000
    
    def test_non_serializable_metadata_fails(self):
        """Non-JSON-serializable metadata fails"""
        class NonSerializable:
            pass
        metadata = {"object": NonSerializable()}
        is_valid, error, _ = validate_metadata_field_size(metadata)
        assert is_valid is False
        assert error is not None
    
    def test_nested_non_serializable_fails(self):
        """Nested non-serializable data fails"""
        metadata = {"nested": {"object": object()}}
        is_valid, error, _ = validate_metadata_field_size(metadata)
        assert is_valid is False
    
    def test_raise_error_flag_raises(self):
        """raise_error=True raises ValidationError"""
        large_metadata = {"data": "x" * (70 * 1024)}
        with pytest.raises(ValidationError) as exc:
            validate_metadata_field_size(large_metadata, max_size_kb=64, raise_error=True)
        assert exc.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_error_includes_size_details(self):
        """ValidationError includes size details"""
        large_metadata = {"data": "x" * (70 * 1024)}
        with pytest.raises(ValidationError) as exc:
            validate_metadata_field_size(large_metadata, max_size_kb=64, raise_error=True)
        assert hasattr(exc.value, 'details')
        if exc.value.details:
            assert 'size_kb' in exc.value.details or 'max_size_kb' in exc.value.details
    
    def test_custom_field_name(self):
        """Custom field_name in error message"""
        large_metadata = {"data": "x" * (70 * 1024)}
        is_valid, error, _ = validate_metadata_field_size(
            large_metadata, 
            max_size_kb=64, 
            field_name="custom_meta"
        )
        assert "custom_meta" in error.lower()
    
    def test_custom_max_size_respected(self):
        """Custom max_size_kb parameter respected"""
        metadata = {"data": "x" * (30 * 1024)}  # 30KB
        # Should pass with 64KB limit
        is_valid1, _, _ = validate_metadata_field_size(metadata, max_size_kb=64)
        assert is_valid1 is True
        # Should fail with 20KB limit
        is_valid2, _, _ = validate_metadata_field_size(metadata, max_size_kb=20)
        assert is_valid2 is False
    
    def test_nested_dict_serializable(self):
        """Nested dict metadata serializable"""
        metadata = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata
    
    def test_list_in_metadata_serializable(self):
        """List values in metadata serializable"""
        metadata = {
            "items": [1, 2, 3, 4, 5],
            "names": ["alice", "bob", "charlie"]
        }
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata
    
    def test_unicode_in_metadata_handled(self):
        """Unicode in metadata handled correctly"""
        metadata = {
            "message": "Hello 世界 🌍",
            "name": "José García"
        }
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata
    
    def test_boolean_and_none_values(self):
        """Boolean and None values in metadata"""
        metadata = {
            "active": True,
            "deleted": False,
            "optional": None
        }
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata
    
    def test_numeric_values_serializable(self):
        """Various numeric types serializable"""
        metadata = {
            "int": 42,
            "float": 3.14,
            "negative": -100,
            "zero": 0
        }
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for content validation"""
    
    def test_content_only_whitespace(self):
        """Content with only whitespace"""
        is_valid, error, normalized = validate_content_length("     ")
        assert is_valid is True
        assert normalized == ""  # Trimmed to empty
    
    def test_content_with_newlines(self):
        """Content with newlines preserved"""
        content = "Line 1\nLine 2\nLine 3"
        is_valid, error, normalized = validate_content_length(content)
        assert is_valid is True
        assert "\n" in normalized
    
    def test_metadata_with_empty_strings(self):
        """Metadata with empty string values"""
        metadata = {"key1": "", "key2": "value", "key3": ""}
        is_valid, error, normalized = validate_metadata_field_size(metadata)
        assert is_valid is True
        assert normalized == metadata
    
    def test_metadata_size_calculated_from_json(self):
        """Metadata size calculated from JSON serialization"""
        # This should be under 64KB
        metadata = {"numbers": list(range(1000))}
        is_valid, error, _ = validate_metadata_field_size(metadata, max_size_kb=64)
        assert is_valid is True