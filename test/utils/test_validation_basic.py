"""
HONEST TEST SUITE: Basic Validation (Phone, Email, Device ID, Input)
======================================================================

Tests basic validation functions: phone, email, device_id, validate_input
Category F: Utils Testing - Group 1/11
Module: message_handler/utils/validation.py
"""

import pytest
import re
from message_handler.utils.validation import (
    validate_input,
    validate_and_raise,
    validate_phone,
    validate_email,
    validate_device_id,
    PHONE_REGEX,
    EMAIL_REGEX,
    UUID_REGEX,
    MAX_PHONE_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_DEVICE_ID_LENGTH
)
from message_handler.exceptions import ValidationError, ErrorCode


# ============================================================================
# TEST: validate_input (base validation function)
# ============================================================================

class TestValidateInput:
    """Test base validate_input function"""
    
    def test_required_field_empty_fails(self):
        """Empty required field fails"""
        is_valid, error, value = validate_input("test_field", "", required=True)
        assert is_valid is False
        assert error is not None
        assert "required" in error.lower()
    
    def test_optional_field_empty_passes(self):
        """Empty optional field passes"""
        is_valid, error, value = validate_input("test_field", "", required=False)
        assert is_valid is True
        assert error is None
    
    def test_max_length_exceeded_fails(self):
        """Value > max_length fails"""
        is_valid, error, _ = validate_input("test", "x" * 100, max_length=50)
        assert is_valid is False
        assert "too long" in error.lower() or "maximum" in error.lower()
    
    def test_min_length_not_met_fails(self):
        """Value < min_length fails"""
        is_valid, error, _ = validate_input("test", "ab", min_length=5)
        assert is_valid is False
        assert "at least" in error.lower()
    
    def test_pattern_match_passes(self):
        """Value matching pattern passes"""
        pattern = re.compile(r'^\d+$')
        is_valid, error, value = validate_input("test", "12345", pattern=pattern)
        assert is_valid is True
        assert value == "12345"
    
    def test_pattern_mismatch_fails(self):
        """Value not matching pattern fails"""
        pattern = re.compile(r'^\d+$')
        is_valid, error, _ = validate_input("test", "abc123", pattern=pattern)
        assert is_valid is False
        assert "invalid format" in error.lower()
    
    def test_string_pattern_auto_compiled(self):
        """String pattern auto-compiled to regex"""
        is_valid, error, _ = validate_input("test", "123", pattern=r'^\d+$')
        assert is_valid is True
    
    def test_value_trimmed(self):
        """Whitespace trimmed from value"""
        is_valid, error, value = validate_input("test", "  hello  ")
        assert value == "hello"
    
    def test_custom_error_message_used(self):
        """Custom error message overrides default"""
        custom = "Custom error"
        is_valid, error, _ = validate_input("test", "", required=True, custom_error_message=custom)
        assert error == custom


class TestValidateAndRaise:
    """Test validate_and_raise (raises on failure)"""
    
    def test_valid_input_returns_normalized(self):
        """Valid input returns normalized value"""
        result = validate_and_raise("test", "  hello  ", max_length=50)
        assert result == "hello"
    
    def test_invalid_raises_validation_error(self):
        """Invalid input raises ValidationError"""
        with pytest.raises(ValidationError) as exc:
            validate_and_raise("test", "", required=True)
        assert exc.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_error_includes_field_name(self):
        """ValidationError includes field name"""
        with pytest.raises(ValidationError) as exc:
            validate_and_raise("username", "", required=True)
        assert "username" in str(exc.value)
    
    def test_error_includes_details(self):
        """ValidationError includes details dict"""
        with pytest.raises(ValidationError) as exc:
            validate_and_raise("test", "x" * 200, max_length=100)
        assert hasattr(exc.value, 'details')


# ============================================================================
# TEST: validate_phone (E.164 format)
# ============================================================================

class TestValidatePhone:
    """Test phone validation with E.164 format"""
    
    @pytest.mark.parametrize("phone", [
        "+1234567890",
        "+441234567890",
        "+919876543210",
        "+8612345678901",
        "+12",  # Minimum valid
    ])
    def test_valid_phones_pass(self, phone):
        """Valid E.164 phones pass"""
        is_valid, error, normalized = validate_phone(phone)
        assert is_valid is True
        assert error is None
        assert normalized == phone
    
    @pytest.mark.parametrize("phone", [
        "1234567890",      # Missing +
        "+0123456789",     # Starts with 0
        "+123abc4567",     # Contains letters
        "++1234567890",    # Double +
        "+1 234 567 890",  # Contains spaces
        "+1-234-567-890",  # Contains hyphens
        "+1234567890123456",  # Too long
        "+1",              # Too short
    ])
    def test_invalid_phones_fail(self, phone):
        """Invalid phones fail"""
        is_valid, error, _ = validate_phone(phone)
        assert is_valid is False
        assert error is not None
    
    def test_empty_required_fails(self):
        """Empty required phone fails"""
        is_valid, error, _ = validate_phone("", required=True)
        assert is_valid is False
    
    def test_empty_optional_passes(self):
        """Empty optional phone passes"""
        is_valid, error, normalized = validate_phone("", required=False)
        assert is_valid is True
        assert normalized == ""
    
    def test_phone_too_long_fails(self):
        """Phone > MAX_PHONE_LENGTH fails"""
        long_phone = "+" + "1" * (MAX_PHONE_LENGTH + 1)
        is_valid, error, _ = validate_phone(long_phone)
        assert is_valid is False
    
    def test_raise_error_flag(self):
        """raise_error=True raises ValidationError"""
        with pytest.raises(ValidationError):
            validate_phone("invalid", raise_error=True)


# ============================================================================
# TEST: validate_email
# ============================================================================

class TestValidateEmail:
    """Test email validation"""
    
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "test.user@example.com",
        "user+tag@example.co.uk",
        "user_name@example-domain.com",
        "123@example.com",
        "a@b.co",
    ])
    def test_valid_emails_pass(self, email):
        """Valid emails pass"""
        is_valid, error, normalized = validate_email(email)
        assert is_valid is True
        assert error is None
        assert normalized == email
    
    @pytest.mark.parametrize("email", [
        "invalid",           # No @
        "@example.com",      # Missing local
        "user@",             # Missing domain
        "user @example.com", # Space in local
        "user@@example.com", # Double @
        "user@.com",         # Domain starts with dot
        "user@example",      # No TLD
    ])
    def test_invalid_emails_fail(self, email):
        """Invalid emails fail"""
        is_valid, error, _ = validate_email(email)
        assert is_valid is False
        assert error is not None
    
    def test_email_too_long_fails(self):
        """Email > MAX_EMAIL_LENGTH fails (FIXED)"""
        # Create email that's ACTUALLY too long
        long_email = "a" * (MAX_EMAIL_LENGTH + 1) + "@test.com"  # Changed from -10 to +1
        is_valid, error, _ = validate_email(long_email)
        assert is_valid is False
    
    def test_empty_required_fails(self):
        """Empty required email fails"""
        is_valid, error, _ = validate_email("", required=True)
        assert is_valid is False
    
    def test_empty_optional_passes(self):
        """Empty optional email passes"""
        is_valid, error, normalized = validate_email("", required=False)
        assert is_valid is True
        assert normalized == ""


# ============================================================================
# TEST: validate_device_id
# ============================================================================

class TestValidateDeviceId:
    """Test device ID validation"""
    
    def test_valid_device_id_passes(self):
        """Valid device ID passes"""
        is_valid, error, normalized = validate_device_id("device-abc-123")
        assert is_valid is True
        assert error is None
        assert normalized == "device-abc-123"
    
    def test_device_id_too_long_fails(self):
        """Device ID > MAX_DEVICE_ID_LENGTH fails"""
        long_id = "x" * (MAX_DEVICE_ID_LENGTH + 1)
        is_valid, error, _ = validate_device_id(long_id)
        assert is_valid is False
    
    def test_empty_required_fails(self):
        """Empty required device ID fails"""
        is_valid, error, _ = validate_device_id("", required=True)
        assert is_valid is False
    
    def test_empty_optional_passes(self):
        """Empty optional device ID passes"""
        is_valid, error, normalized = validate_device_id("", required=False)
        assert is_valid is True
        assert normalized == ""
    
    def test_device_id_trimmed(self):
        """Device ID whitespace trimmed"""
        is_valid, error, normalized = validate_device_id("  device-123  ")
        assert normalized == "device-123"


# ============================================================================
# TEST: Regex Patterns
# ============================================================================

class TestRegexPatterns:
    """Test regex pattern constants"""
    
    def test_phone_regex_valid(self):
        """PHONE_REGEX matches valid E.164"""
        assert PHONE_REGEX.match("+1234567890") is not None
        assert PHONE_REGEX.match("+919876543210") is not None
    
    def test_phone_regex_invalid(self):
        """PHONE_REGEX rejects invalid"""
        assert PHONE_REGEX.match("1234567890") is None
        assert PHONE_REGEX.match("+0123456789") is None
    
    def test_email_regex_valid(self):
        """EMAIL_REGEX matches valid emails"""
        assert EMAIL_REGEX.match("user@example.com") is not None
    
    def test_email_regex_invalid(self):
        """EMAIL_REGEX rejects invalid"""
        assert EMAIL_REGEX.match("invalid") is None
        assert EMAIL_REGEX.match("@example.com") is None
    
    def test_uuid_regex_valid(self):
        """UUID_REGEX matches valid UUID"""
        assert UUID_REGEX.match("550e8400-e29b-41d4-a716-446655440000") is not None
    
    def test_uuid_regex_invalid(self):
        """UUID_REGEX rejects invalid"""
        assert UUID_REGEX.match("not-a-uuid") is None


# ============================================================================
# TEST: Constants
# ============================================================================

class TestConstants:
    """Test validation constants"""
    
    def test_max_lengths_defined(self):
        """Max length constants defined"""
        assert MAX_PHONE_LENGTH == 32
        assert MAX_EMAIL_LENGTH == 128
        assert MAX_DEVICE_ID_LENGTH == 128
    
    def test_constants_positive(self):
        """Constants are positive integers"""
        assert MAX_PHONE_LENGTH > 0
        assert MAX_EMAIL_LENGTH > 0
        assert MAX_DEVICE_ID_LENGTH > 0