"""Request models for API endpoints."""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class UserDetails(BaseModel):
    """User identification details."""
    phone_e164: Optional[str] = Field(None, description="E.164 formatted phone number")
    email: Optional[str] = Field(None, description="Email address")
    device_id: Optional[str] = Field(None, description="Device identifier")
    auth_token: Optional[str] = Field(None, description="Authentication token")

    class Config:
        extra = "allow"  # Allow extra fields so they can be stripped by sanitize_data

    @field_validator('phone_e164')
    @classmethod
    def validate_phone_format(cls, v):
        """Validate phone number format (E.164)."""
        if v is None:
            return v
        # E.164 format: + followed by 1-15 digits
        phone_pattern = re.compile(r'^\+[1-9][0-9]{1,14}$')
        if not phone_pattern.match(v):
            raise ValueError("phone_e164 must be in E.164 format (e.g., +1234567890)")
        # Check for SQL injection patterns
        if any(dangerous in v.lower() for dangerous in ["drop", "select", "insert", "delete", "update", "union", "--", ";"]):
            raise ValueError("phone_e164 contains invalid characters")
        return v

    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v):
        """Validate email format."""
        if v is None:
            return v
        # Basic email validation
        email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
        if not email_pattern.match(v):
            raise ValueError("Invalid email address format")
        # Check length
        if len(v) > 128:
            raise ValueError("email exceeds maximum length of 128 characters")
        # Check for SQL injection patterns
        if any(dangerous in v.lower() for dangerous in ["drop", "select", "insert", "delete", "update", "union", "--", ";"]):
            raise ValueError("email contains invalid characters")
        return v


class MessageRequest(BaseModel):
    """Standard message request."""
    content: str = Field(..., description="Message content", min_length=1)
    instance_id: str = Field(..., description="Instance ID")
    user_details: Optional[UserDetails] = Field(None, description="User details for authentication")
    request_id: str = Field(..., description="Client-provided unique request ID for idempotency", min_length=1, max_length=128)
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")
    
    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v):
        """Validate request_id format."""
        if not v or not v.strip():
            raise ValueError("request_id cannot be empty")
        if len(v) > 128:
            raise ValueError("request_id exceeds maximum length of 128 characters")
        # Basic format validation - alphanumeric, dash, underscore, dot only
        if not re.match(r'^[a-zA-Z0-9\-_\.]+$', v):
            raise ValueError("request_id contains invalid characters (use alphanumeric, dash, underscore, dot only)")
        return v.strip()


class WhatsAppMessageRequest(BaseModel):
    """WhatsApp-specific message request."""
    message: Dict[str, Any] = Field(..., description="WhatsApp message object")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    instance_id: Optional[str] = Field(None, description="Instance ID (if not in metadata)")
    request_id: str = Field(..., description="Client-provided unique request ID for idempotency", min_length=1, max_length=128)
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")
    
    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v):
        """Validate request_id format."""
        if not v or not v.strip():
            raise ValueError("request_id cannot be empty")
        if len(v) > 128:
            raise ValueError("request_id exceeds maximum length of 128 characters")
        if not re.match(r'^[a-zA-Z0-9\-_\.]+$', v):
            raise ValueError("request_id contains invalid characters")
        return v.strip()


class BroadcastRequest(BaseModel):
    """Broadcast message request."""
    instance_id: str = Field(..., description="Instance ID")
    content: str = Field(..., description="Message content", min_length=1)
    user_ids: List[str] = Field(..., description="List of user IDs to send to", min_items=1)
    request_id: str = Field(..., description="Base request ID for broadcast (will be scoped per user)", min_length=1, max_length=128)
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")
    
    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v):
        """Validate request_id format."""
        if not v or not v.strip():
            raise ValueError("request_id cannot be empty")
        if len(v) > 128:
            raise ValueError("request_id exceeds maximum length of 128 characters")
        if not re.match(r'^[a-zA-Z0-9\-_\.]+$', v):
            raise ValueError("request_id contains invalid characters")
        return v.strip()