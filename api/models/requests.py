"""Request models for API endpoints."""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class UserDetails(BaseModel):
    """User identification details."""
    phone_e164: Optional[str] = Field(None, description="E.164 formatted phone number")
    email: Optional[str] = Field(None, description="Email address")
    device_id: Optional[str] = Field(None, description="Device identifier")
    auth_token: Optional[str] = Field(None, description="Authentication token")


class MessageRequest(BaseModel):
    """Standard message request."""
    content: str = Field(..., description="Message content", min_length=1)
    instance_id: str = Field(..., description="Instance ID")
    user: Optional[UserDetails] = Field(None, description="User details for authentication")
    idempotency_key: Optional[str] = Field(None, description="Unique key for idempotency")
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")


class WhatsAppMessageRequest(BaseModel):
    """WhatsApp-specific message request."""
    message: Dict[str, Any] = Field(..., description="WhatsApp message object")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    instance_id: Optional[str] = Field(None, description="Instance ID (if not in metadata)")
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")


class BroadcastRequest(BaseModel):
    """Broadcast message request."""
    instance_id: str = Field(..., description="Instance ID")
    content: str = Field(..., description="Message content", min_length=1)
    user_ids: List[str] = Field(..., description="List of user IDs to send to", min_items=1)
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")