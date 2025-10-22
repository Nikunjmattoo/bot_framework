"""
Main entry point for message handling - delegates to specialized handlers.

This module provides the main interface for processing messages from
different channels, delegating to specialized handlers based on the 
message type and channel.
"""
import time
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple, cast
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.handlers.api_handler import process_api_message
from message_handler.handlers.whatsapp_handler import (
    process_whatsapp_message_internal,
    validate_whatsapp_message
)
from message_handler.handlers.broadcast_handler import broadcast_message_internal
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError,
    OrchestrationError, DuplicateError, ErrorCode
)
from message_handler.utils.error_handling import handle_database_error, with_error_handling
from message_handler.utils.data_utils import sanitize_data

# Get the package version
try:
    from message_handler.version import __version__
except ImportError:
    __version__ = "unknown"

# Constants
MAX_CONTENT_LENGTH = 10000


def validate_message_content(content: str) -> bool:
    """
    Validate message content for length and basic format requirements.
    
    Args:
        content: Message content to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If validation fails with detailed information
    """
    if not content or not content.strip():
        raise ValidationError(
            "Message content cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content"
        )
    
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValidationError(
            f"Message content exceeds maximum length of {MAX_CONTENT_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content",
            details={"length": len(content), "max_length": MAX_CONTENT_LENGTH}
        )
    
    return True


def get_handler_status() -> Dict[str, Any]:
    """
    Get status information about the message handler.
    
    Returns:
        Dict with status information including:
        - version: Handler version
        - available_channels: List of supported channels
        - health: Health status information
    """
    return {
        "name": "message_handler",
        "version": __version__,
        "status": "operational",
        "available_channels": ["api", "web", "app", "whatsapp", "broadcast"],
        "health": {
            "status": "healthy",
            "timestamp": time.time()
        }
    }


@with_error_handling(
    operation_name="process_message",
    reraise=[ValidationError, ResourceNotFoundError, OrchestrationError, DuplicateError]
)
def process_message(
    db: Session,
    content: str,
    instance_id: str,
    user_details: Optional[Dict[str, Any]] = None,
    request_id: str = None,  # NOW REQUIRED (but keeping Optional for backward compat check)
    trace_id: Optional[str] = None,
    channel: str = "api"
) -> Dict[str, Any]:
    """
    Process an incoming message from API/web/app channels.
    
    This is the main entry point for processing messages from API, web,
    and app channels. It validates inputs, then delegates to the appropriate
    channel-specific handler.
    
    Args:
        db: Database session
        content: Message content
        instance_id: Instance ID
        user_details: User details (optional)
        request_id: Client-provided request ID (REQUIRED)
        trace_id: Trace ID for logging (optional)
        channel: Channel (default: "api")
        
    Returns:
        Result data dict with message ID and response information
        
    Raises:
        ValidationError: If message validation fails
        ResourceNotFoundError: If instance or user not found
        OrchestrationError: If orchestration fails
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "message_handler", 
        trace_id=trace_id,
        instance_id=instance_id,
        channel=channel,
        request_id=request_id
    )
    
    # Validate inputs before delegating
    if not instance_id:
        raise ValidationError(
            "Instance ID is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )
    
    # Validate request_id (REQUIRED for Option B)
    if not request_id:
        raise ValidationError(
            "request_id is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="request_id"
        )
    
    # Validate content
    validate_message_content(content)
    
    # Sanitize user_details
    sanitized_user_details = sanitize_data(
        user_details or {},
        strip_keys=["password", "token", "secret", "auth"],
        max_string_length=1024
    )
    
    # Log the request
    logger.info(f"Processing message through {channel} channel")
    
    # Delegate to API handler
    result = process_api_message(
        db=db,
        content=content,
        instance_id=instance_id,
        user_details=sanitized_user_details,
        request_id=request_id,
        trace_id=trace_id,
        channel=channel
    )
    
    # Add performance metrics
    processing_time = time.time() - start_time
    
    if isinstance(result, dict) and "_meta" not in result:
        result["_meta"] = {
            "processing_time_seconds": round(processing_time, 3),
            "trace_id": trace_id,
            "channel": channel,
            "handler_version": __version__
        }
    
    logger.info(f"Message processed in {processing_time:.3f}s")
    
    return result


@with_error_handling(
    operation_name="process_whatsapp_message",
    reraise=[ValidationError, ResourceNotFoundError, OrchestrationError, DuplicateError]
)
def process_whatsapp_message(
    db: Session,
    whatsapp_message: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    instance_id: Optional[str] = None,
    request_id: str = None,  # NOW REQUIRED
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a WhatsApp message.
    
    This is the main entry point for processing messages from WhatsApp.
    It validates inputs, then delegates to the WhatsApp-specific handler.
    
    Args:
        db: Database session
        whatsapp_message: WhatsApp message object
        metadata: Additional metadata (optional)
        instance_id: Instance ID (optional)
        request_id: Client-provided request ID (REQUIRED)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Result data dict with message ID and response information
        
    Raises:
        ValidationError: If message validation fails
        ResourceNotFoundError: If instance or user not found
        OrchestrationError: If orchestration fails
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "message_handler", 
        trace_id=trace_id,
        channel="whatsapp",
        request_id=request_id
    )
    
    # Validate inputs before delegating
    if not whatsapp_message:
        raise ValidationError(
            "WhatsApp message cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="whatsapp_message"
        )
    
    # Validate request_id (REQUIRED)
    if not request_id:
        raise ValidationError(
            "request_id is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="request_id"
        )
    
    # Sanitize whatsapp_message and metadata
    sanitized_whatsapp_message = sanitize_data(
        whatsapp_message,
        strip_keys=["password", "token", "secret", "auth"],
        max_string_length=1024
    )
    
    sanitized_metadata = sanitize_data(
        metadata or {},
        max_string_length=1024
    )
    
    # Do a basic validation of WhatsApp message structure
    validate_whatsapp_message(sanitized_whatsapp_message, sanitized_metadata, trace_id)
    
    # Log the request
    logger.info("Processing WhatsApp message")
    
    # Delegate to WhatsApp handler
    result = process_whatsapp_message_internal(
        db=db,
        whatsapp_message=sanitized_whatsapp_message,
        metadata=sanitized_metadata,
        instance_id=instance_id,
        request_id=request_id,
        trace_id=trace_id
    )
    
    # Add performance metrics
    processing_time = time.time() - start_time
    
    if isinstance(result, dict) and "_meta" not in result:
        result["_meta"] = {
            "processing_time_seconds": round(processing_time, 3),
            "trace_id": trace_id,
            "channel": "whatsapp",
            "handler_version": __version__
        }
    
    logger.info(f"WhatsApp message processed in {processing_time:.3f}s")
    
    return result


@with_error_handling(
    operation_name="broadcast_message",
    reraise=[ValidationError, ResourceNotFoundError, DuplicateError]
)
def broadcast_message(
    db: Session,
    content: str,
    instance_id: str,
    user_ids: List[str],
    request_id: str = None,  # NOW REQUIRED (base request_id for broadcast)
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Broadcast a message to multiple users.
    
    This is the main entry point for broadcasting messages to multiple users.
    It validates inputs, then delegates to the broadcast handler.
    
    Args:
        db: Database session
        content: Message content
        instance_id: Instance ID
        user_ids: List of user IDs to send to
        request_id: Base request ID for broadcast (REQUIRED)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Dict with broadcast results and summary statistics
        
    Raises:
        ValidationError: If message validation fails
        ResourceNotFoundError: If instance not found
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "message_handler", 
        trace_id=trace_id,
        instance_id=instance_id,
        channel="broadcast",
        request_id=request_id
    )
    
    # Validate inputs before delegating
    if not instance_id:
        raise ValidationError(
            "Instance ID is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )
    
    # Validate request_id (REQUIRED)
    if not request_id:
        raise ValidationError(
            "request_id is required for broadcast",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="request_id"
        )
    
    # Validate content
    validate_message_content(content)
    
    # Validate user IDs
    if not user_ids:
        raise ValidationError(
            "User IDs list cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="user_ids"
        )
    
    # Sanitize user_ids list
    sanitized_user_ids = sanitize_data(
        user_ids,
        max_list_items=1000
    )
    
    # Log the request
    logger.info(f"Broadcasting message to {len(sanitized_user_ids)} users")
    
    # Delegate to broadcast handler
    result = broadcast_message_internal(
        db=db,
        content=content,
        instance_id=instance_id,
        user_ids=sanitized_user_ids,
        request_id=request_id,
        trace_id=trace_id
    )
    
    # Add performance metrics if not already present
    processing_time = time.time() - start_time
    
    if isinstance(result, dict):
        if "summary" in result and isinstance(result["summary"], dict) and "_meta" not in result["summary"]:
            result["summary"]["_meta"] = {
                "processing_time_seconds": round(processing_time, 3),
                "trace_id": trace_id,
                "handler_version": __version__
            }
        elif "_meta" not in result:
            result["_meta"] = {
                "processing_time_seconds": round(processing_time, 3),
                "trace_id": trace_id,
                "channel": "broadcast",
                "handler_version": __version__
            }
    
    logger.info(f"Broadcast completed in {processing_time:.3f}s")
    
    return result