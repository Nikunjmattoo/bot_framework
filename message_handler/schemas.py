"""
Schema definitions for message handling.

Provides validation models for incoming message data.
"""
from __future__ import annotations
from typing import Optional, List, Literal, Dict, Any, Union, Set, ClassVar, cast
import re
from datetime import datetime, timezone
import json
from enum import Enum

# Use pydantic if available, otherwise create basic validation classes
try:
    from pydantic import (
        BaseModel, Field, EmailStr, model_validator, field_validator,
        HttpUrl, constr, conint, AnyUrl
    )
except ImportError:
    # Create fallback classes if pydantic isn't available
    class BaseModel:
        """Basic model class that mimics pydantic BaseModel."""
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)
                
    # Dummy classes to make imports work
    Field = lambda *args, **kwargs: None
    EmailStr = str
    model_validator = lambda *args, **kwargs: lambda func: func
    field_validator = lambda *args, **kwargs: lambda func: func
    HttpUrl = str
    constr = lambda *args, **kwargs: str
    conint = lambda *args, **kwargs: int
    AnyUrl = str

# Import validation utilities
from message_handler.utils.validation import (
    validate_phone, validate_email, validate_device_id,
    validate_content_length, validate_metadata_field_size,
    MAX_PHONE_LENGTH, MAX_EMAIL_LENGTH, MAX_DEVICE_ID_LENGTH, MAX_MESSAGE_LENGTH
)

# Configuration constants
MAX_METADATA_SIZE_KB = 64  # Maximum metadata size in KB
ALLOWED_MIME_TYPES = {
    "application/pdf", "image/jpeg", "image/png", "image/gif", 
    "text/plain", "text/csv", "application/json"
}

class Channel(str, Enum):
    """Supported message channels."""
    WHATSAPP = "whatsapp"
    WEB = "web"
    APP = "app"
    API = "api"
    BROADCAST = "broadcast"


class AttachmentType(str, Enum):
    """Supported attachment types."""
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class Attachment(BaseModel):
    """Attachment model with enhanced validation."""
    type: AttachmentType = AttachmentType.FILE
    url: str  # URL to the attachment
    name: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None  # Must be positive if provided
    
    # List of allowed MIME types (can be overridden)
    allowed_mime_types: ClassVar[Set[str]] = ALLOWED_MIME_TYPES
    
    @field_validator('mime')
    @classmethod
    def validate_mime_type(cls, v):
        """Validate that mime type is allowed if provided."""
        if v is not None and v not in cls.allowed_mime_types:
            allowed_list = ", ".join(sorted(cls.allowed_mime_types))
            raise ValueError(
                f"Unsupported MIME type: {v}. Allowed types: {allowed_list}"
            )
        return v

    @field_validator('name')
    @classmethod
    def sanitize_filename(cls, v):
        """Sanitize filename to prevent path traversal attacks."""
        if v is None:
            return v
        
        # Remove any directory components
        clean_name = re.sub(r'[/\\]', '', v)
        
        # Limit length
        if len(clean_name) > 255:
            clean_name = clean_name[:255]
            
        return clean_name
        
    @field_validator('size')
    @classmethod
    def validate_size(cls, v):
        """Validate size is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Size must be a positive integer")
        return v
        
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Basic URL validation."""
        if not v:
            raise ValueError("URL is required")
            
        # Basic URL validation
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("URL must start with http:// or https://")
            
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "file",
                    "url": "https://example.com/files/document.pdf",
                    "name": "document.pdf",
                    "mime": "application/pdf",
                    "size": 1024567
                }
            ]
        }
    }


class InboundMessage(BaseModel):
    """Inbound message model with enhanced validation."""
    # Channel + addressing
    channel: Channel
    instance_id: Optional[str] = None
    recipient_number: Optional[str] = None
    
    # User identifiers (web/app can use any one)
    sender_number: Optional[str] = None
    email: Optional[str] = None
    device_id: Optional[str] = None
    # Optional: brand-asserted phone for web/app
    brand_asserted_sender_number: Optional[str] = None

    # Idempotency (web/app should pass this; WA will rely on provider id)
    client_request_id: Optional[str] = None

    # Content
    message: Optional[str] = Field(default="")
    attachments: List[Attachment] = Field(default_factory=list)

    # Optional metadata
    provider_message_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Maximum number of attachments
    max_attachments: ClassVar[int] = 10

    # Email validation using utility
    @field_validator('email')
    @classmethod
    def validate_email_field(cls, v):
        """Validate email format and length."""
        if not v:
            return v
            
        is_valid, error_msg, normalized = validate_email(v, required=False)
        if not is_valid:
            raise ValueError(error_msg)
            
        return normalized

    # Device ID validation using utility
    @field_validator('device_id')
    @classmethod
    def validate_device_id_field(cls, v):
        """Validate device ID format and length."""
        if not v:
            return v
            
        is_valid, error_msg, normalized = validate_device_id(v, required=False)
        if not is_valid:
            raise ValueError(error_msg)
            
        return normalized

    # Phone number validation using utility
    @field_validator('sender_number', 'recipient_number', 'brand_asserted_sender_number')
    @classmethod
    def validate_phone_field(cls, v):
        """Validate phone number format and length."""
        if not v:
            return v
            
        is_valid, error_msg, normalized = validate_phone(v, required=False)
        if not is_valid:
            raise ValueError(error_msg)
            
        return normalized
        
    # Attachments validation
    @field_validator('attachments')
    @classmethod
    def validate_attachments(cls, attachments_list):
        """Validate attachment count and size."""
        if len(attachments_list) > cls.max_attachments:
            raise ValueError(f"Too many attachments. Maximum allowed: {cls.max_attachments}")
        return attachments_list
        
    # Message content validation using utility
    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v):
        """Normalize and validate message content."""
        if v is None:
            return ""
            
        is_valid, error_msg, normalized = validate_content_length(
            v, max_length=MAX_MESSAGE_LENGTH, field_name="message", required=False
        )
        
        if not is_valid:
            raise ValueError(error_msg)
            
        return normalized
        
    # Metadata size validation
    @field_validator('metadata')
    @classmethod
    def validate_metadata_size(cls, v):
        """Validate metadata size."""
        is_valid, error_msg, normalized = validate_metadata_field_size(
            v, 
            max_size_kb=MAX_METADATA_SIZE_KB,
            field_name="metadata"
        )
        
        if not is_valid:
            raise ValueError(error_msg)
            
        return normalized
    
    # Instance ID validation
    @field_validator('instance_id')
    @classmethod
    def validate_instance_id(cls, v):
        """Validate instance ID."""
        if v is not None:
            try:
                # Validate UUID format if string looks like a UUID
                if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', v.lower()):
                    # This is a UUID format, parse it to validate
                    import uuid
                    uuid.UUID(v)
            except (ValueError, AttributeError):
                raise ValueError("Instance ID must be a valid identifier")
        return v

    # Conditional validation rules
    @model_validator(mode="after")
    def check_required_by_channel(self) -> "InboundMessage":
        """Validate required fields based on channel."""
        ch = self.channel

        if ch == Channel.WHATSAPP:
            # Only trust webhook numbers on WA
            self.brand_asserted_sender_number = None
            
            if not self.sender_number:
                raise ValueError("sender_number is required for WhatsApp channel")
                
            if not self.recipient_number:
                raise ValueError("recipient_number is required for WhatsApp channel")

        elif ch in (Channel.WEB, Channel.APP, Channel.API):
            if not self.instance_id:
                raise ValueError(f"instance_id is required for {ch.value} channel")
                
            if not any([self.email, self.sender_number, self.device_id, self.brand_asserted_sender_number]):
                raise ValueError(
                    f"At least one identifier (email, sender_number, device_id, or brand_asserted_sender_number) "
                    f"is required for {ch.value} channel"
                )

        elif ch == Channel.BROADCAST:
            if not self.instance_id:
                raise ValueError("instance_id is required for broadcast channel")

        return self
        
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "channel": "web",
                    "instance_id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "message": "Hello, this is a test message",
                    "client_request_id": "client-123456"
                },
                {
                    "channel": "whatsapp",
                    "sender_number": "+1234567890",
                    "recipient_number": "+9876543210",
                    "message": "Hello via WhatsApp",
                    "provider_message_id": "wamid.abcd1234"
                }
            ]
        }
    }


# Export additional models for API responses
class MessageResponse(BaseModel):
    """Response model for message processing."""
    message_id: str
    session_id: Optional[str] = None
    response: Dict[str, Any]
    
    # Timestamp for when the response was generated
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message_id": "550e8400-e29b-41d4-a716-446655440000",
                    "session_id": "660e8400-e29b-41d4-a716-446655440001",
                    "response": {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "content": "Hello! How can I help you today?"
                    },
                    "timestamp": "2025-03-15T12:34:56.789012Z"
                }
            ]
        }
    }


class BroadcastResponse(BaseModel):
    """Response model for broadcast operations."""
    summary: Dict[str, Any]
    results: List[Dict[str, Any]]
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": {
                        "total": 3,
                        "successful": 2,
                        "failed": 1,
                        "processing_time_seconds": 1.234
                    },
                    "results": [
                        {
                            "user_id": "user-1",
                            "success": True,
                            "message_id": "msg-1",
                            "session_id": "session-1"
                        },
                        {
                            "user_id": "user-2",
                            "success": True,
                            "message_id": "msg-2",
                            "session_id": "session-2"
                        },
                        {
                            "user_id": "user-3",
                            "success": False,
                            "error": "User not found"
                        }
                    ]
                }
            ]
        }
    }