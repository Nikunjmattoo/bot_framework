"""
Validation utilities for the message handler system.

This module provides common validation functions used throughout
the message handler codebase.
"""
import re
from typing import Optional, Pattern, Tuple, Union, Dict, Any

from message_handler.exceptions import ValidationError, ErrorCode
import json

def validate_input(
    field_name: str,
    value: str,
    required: bool = True,
    max_length: Optional[int] = None,
    min_length: Optional[int] = None,
    pattern: Optional[Union[str, Pattern]] = None,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    custom_error_message: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Validate an input string against common validation rules.
    
    Args:
        field_name: Name of the field being validated (for error messages)
        value: Value to validate
        required: Whether the field is required (default: True)
        max_length: Maximum allowed length (optional)
        min_length: Minimum required length (optional)
        pattern: Regex pattern to match (optional)
        error_code: Error code to use if validation fails (default: VALIDATION_ERROR)
        custom_error_message: Optional custom error message
        
    Returns:
        Tuple of (is_valid, error_message, normalized_value)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    # Handle empty values
    if not value:
        if required:
            error_msg = custom_error_message or f"{field_name} is required"
            return False, error_msg, ""
        return True, None, ""
    
    # Normalize value
    normalized_value = str(value).strip()
    
    # Check minimum length
    if min_length is not None and len(normalized_value) < min_length:
        error_msg = custom_error_message or f"{field_name} must be at least {min_length} characters"
        return False, error_msg, normalized_value
    
    # Check maximum length
    if max_length is not None and len(normalized_value) > max_length:
        error_msg = custom_error_message or f"{field_name} is too long (maximum {max_length} characters)"
        return False, error_msg, normalized_value
    
    # Check pattern
    if pattern:
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        
        if not pattern.match(normalized_value):
            error_msg = custom_error_message or f"{field_name} has invalid format"
            return False, error_msg, normalized_value
    
    return True, None, normalized_value


def validate_and_raise(
    field_name: str,
    value: str,
    required: bool = True,
    max_length: Optional[int] = None,
    min_length: Optional[int] = None,
    pattern: Optional[Union[str, Pattern]] = None,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    custom_error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Validate an input and raise ValidationError if invalid.
    
    Args:
        field_name: Name of the field being validated
        value: Value to validate
        required: Whether the field is required (default: True)
        max_length: Maximum allowed length (optional)
        min_length: Minimum required length (optional)
        pattern: Regex pattern to match (optional)
        error_code: Error code to use if validation fails (default: VALIDATION_ERROR)
        custom_error_message: Optional custom error message
        details: Additional details for the error (optional)
        
    Returns:
        Normalized value if valid
        
    Raises:
        ValidationError: If validation fails
    """
    is_valid, error_message, normalized_value = validate_input(
        field_name=field_name,
        value=value,
        required=required,
        max_length=max_length,
        min_length=min_length,
        pattern=pattern,
        error_code=error_code,
        custom_error_message=custom_error_message
    )
    
    if not is_valid:
        error_details = details or {}
        if max_length is not None:
            error_details["max_length"] = max_length
        if min_length is not None:
            error_details["min_length"] = min_length
        if value is not None:
            error_details["value"] = str(value)
            
        raise ValidationError(
            error_message,
            error_code=error_code,
            field=field_name,
            details=error_details
        )
        
    return normalized_value


# Common validation patterns
PHONE_REGEX = re.compile(r'^\+[1-9][0-9]{1,14}$')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

# Common validation constants
MAX_PHONE_LENGTH = 32
MAX_EMAIL_LENGTH = 128
MAX_DEVICE_ID_LENGTH = 128
MAX_MESSAGE_LENGTH = 10000


def validate_phone(
    phone: str,
    field_name: str = "phone",
    required: bool = True,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    raise_error: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Validate a phone number.
    
    Args:
        phone: Phone number to validate
        field_name: Field name for error messages (default: "phone")
        required: Whether the phone is required (default: True)
        error_code: Error code to use if validation fails
        raise_error: Whether to raise an exception if validation fails
        
    Returns:
        Tuple of (is_valid, error_message, normalized_phone)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    result = validate_input(
        field_name=field_name,
        value=phone,
        required=required,
        max_length=MAX_PHONE_LENGTH,
        pattern=PHONE_REGEX,
        error_code=error_code,
        custom_error_message=f"{field_name} must be in E.164 format (e.g., +1234567890)"
    )
    
    if not result[0] and raise_error:
        validate_and_raise(
            field_name=field_name,
            value=phone,
            required=required,
            max_length=MAX_PHONE_LENGTH,
            pattern=PHONE_REGEX,
            error_code=error_code,
            custom_error_message=result[1]
        )
        
    return result


def validate_email(
    email: str,
    field_name: str = "email",
    required: bool = True,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    raise_error: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Validate an email address.
    
    Args:
        email: Email address to validate
        field_name: Field name for error messages (default: "email")
        required: Whether the email is required (default: True)
        error_code: Error code to use if validation fails
        raise_error: Whether to raise an exception if validation fails
        
    Returns:
        Tuple of (is_valid, error_message, normalized_email)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    result = validate_input(
        field_name=field_name,
        value=email,
        required=required,
        max_length=MAX_EMAIL_LENGTH,
        pattern=EMAIL_REGEX,
        error_code=error_code,
        custom_error_message=f"Invalid {field_name} address format"
    )
    
    if not result[0] and raise_error:
        validate_and_raise(
            field_name=field_name,
            value=email,
            required=required,
            max_length=MAX_EMAIL_LENGTH,
            pattern=EMAIL_REGEX,
            error_code=error_code,
            custom_error_message=result[1]
        )
        
    return result


def validate_device_id(
    device_id: str,
    field_name: str = "device_id",
    required: bool = True,
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    raise_error: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Validate a device ID.
    
    Args:
        device_id: Device ID to validate
        field_name: Field name for error messages (default: "device_id")
        required: Whether the device_id is required (default: True)
        error_code: Error code to use if validation fails
        raise_error: Whether to raise an exception if validation fails
        
    Returns:
        Tuple of (is_valid, error_message, normalized_device_id)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    result = validate_input(
        field_name=field_name,
        value=device_id,
        required=required,
        max_length=MAX_DEVICE_ID_LENGTH,
        error_code=error_code
    )
    
    if not result[0] and raise_error:
        validate_and_raise(
            field_name=field_name,
            value=device_id,
            required=required,
            max_length=MAX_DEVICE_ID_LENGTH,
            error_code=error_code,
            custom_error_message=result[1]
        )
        
    return result


def validate_content_length(
    content: str,
    max_length: int = MAX_MESSAGE_LENGTH,
    field_name: str = "content",
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    raise_error: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Validate and normalize content length.
    
    Args:
        content: Content to validate
        max_length: Maximum allowed length (default: MAX_MESSAGE_LENGTH)
        field_name: Field name for error messages (default: "content")
        error_code: Error code to use if validation fails
        raise_error: Whether to raise an exception if validation fails
        
    Returns:
        Tuple of (is_valid, error_message, normalized_content)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    result = validate_input(
        field_name=field_name,
        value=content,
        required=False,  # Allow empty content
        max_length=max_length,
        error_code=error_code,
        custom_error_message=f"{field_name} exceeds maximum length of {max_length} characters"
    )
    
    if not result[0] and raise_error:
        validate_and_raise(
            field_name=field_name,
            value=content,
            required=False,
            max_length=max_length,
            error_code=error_code,
            custom_error_message=result[1],
            details={"length": len(content) if content else 0, "max_length": max_length}
        )
        
    return result

def validate_metadata_field_size(
    metadata: Dict[str, Any],
    max_size_kb: int = 64,
    field_name: str = "metadata",
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    raise_error: bool = False
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate metadata size and truncate if needed.
    
    Args:
        metadata: Metadata dictionary to validate
        max_size_kb: Maximum size in KB (default: 64)
        field_name: Field name for error messages (default: "metadata")
        error_code: Error code to use if validation fails
        raise_error: Whether to raise an exception if validation fails
        
    Returns:
        Tuple of (is_valid, error_message, normalized_metadata)
        
    Raises:
        ValidationError: If raise_error is True and validation fails
    """
    # Handle empty metadata
    if not metadata:
        return True, None, {}
    
    # Default normalized result is the original metadata
    normalized = metadata.copy() if isinstance(metadata, dict) else {}
    
    # Validate it's a dictionary
    if not isinstance(metadata, dict):
        error_msg = f"{field_name} must be a dictionary"
        
        if raise_error:
            raise ValidationError(
                error_msg,
                error_code=error_code,
                field=field_name,
                details={"actual_type": type(metadata).__name__}
            )
            
        return False, error_msg, normalized
    
    # Estimate size by serializing to JSON
    try:
        serialized = json.dumps(metadata)
        size_kb = len(serialized) / 1024
        
        if size_kb > max_size_kb:
            error_msg = f"{field_name} exceeds maximum size of {max_size_kb}KB"
            
            # Create truncated metadata with essential fields
            truncated = {"truncated": True, "original_size_kb": round(size_kb, 1)}
            
            # Preserve some essential fields if they exist
            for key in ["channel", "message_type", "timestamp", "source"]:
                if key in metadata:
                    truncated[key] = metadata[key]
            
            if raise_error:
                raise ValidationError(
                    error_msg,
                    error_code=error_code,
                    field=field_name,
                    details={"size_kb": round(size_kb, 1), "max_size_kb": max_size_kb}
                )
                
            return False, error_msg, truncated
            
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        error_msg = f"Invalid {field_name} format: {str(e)}"
        
        if raise_error:
            raise ValidationError(
                error_msg,
                error_code=error_code,
                field=field_name,
                details={"error": str(e)}
            )
            
        return False, error_msg, {"error": "Invalid format"}
    
    return True, None, normalized