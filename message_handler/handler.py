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
    OrchestrationError, ErrorCode
)

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


def handle_db_error(e: Exception, operation: str, logger: Any, error_code: ErrorCode = ErrorCode.DATABASE_ERROR):
    """
    Standardized handler for database errors.
    
    Args:
        e: Exception that occurred
        operation: Operation that was being performed
        logger: Logger to use
        error_code: Error code to use (default: DATABASE_ERROR)
        
    Raises:
        DatabaseError: Wrapped database error
    """
    error_msg = f"Database error in {operation}: {str(e)}"
    logger.error(error_msg)
    raise DatabaseError(
        error_msg,
        error_code=error_code,
        original_exception=e,
        operation=operation
    )


def process_message(
    db: Session,
    content: str,
    instance_id: str,
    user_details: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
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
        idempotency_key: Idempotency key (optional)
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
        channel=channel
    )
    
    try:
        # Validate inputs before delegating
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Validate content
        validate_message_content(content)
        
        # Normalize user_details
        normalized_user_details = user_details or {}
        
        # Log the request
        logger.info(f"Processing message through {channel} channel")
        
        # Delegate to API handler
        result = process_api_message(
            db=db,
            content=content,
            instance_id=instance_id,
            user_details=normalized_user_details,
            idempotency_key=idempotency_key,
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
        
    except ValidationError:
        # Re-raise validation errors for proper API responses
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except OrchestrationError:
        # Re-raise orchestration errors
        raise
    except SQLAlchemyError as e:
        handle_db_error(e, "process_message", logger)
    except Exception as e:
        error_msg = f"Unexpected error in message handler: {str(e)}"
        logger.exception(error_msg)
        raise OrchestrationError(
            error_msg,
            error_code=ErrorCode.ORCHESTRATION_ERROR,
            original_exception=e
        )


def process_whatsapp_message(
    db: Session,
    whatsapp_message: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    instance_id: Optional[str] = None,
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
        channel="whatsapp"
    )
    
    try:
        # Validate inputs before delegating
        if not whatsapp_message:
            raise ValidationError(
                "WhatsApp message cannot be empty",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="whatsapp_message"
            )
        
        # Do a basic validation of WhatsApp message structure
        validate_whatsapp_message(whatsapp_message, metadata, trace_id)
        
        # Normalize metadata
        normalized_metadata = metadata or {}
        
        # Log the request
        logger.info("Processing WhatsApp message")
        
        # Delegate to WhatsApp handler
        result = process_whatsapp_message_internal(
            db=db,
            whatsapp_message=whatsapp_message,
            metadata=normalized_metadata,
            instance_id=instance_id,
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
        
    except ValidationError:
        # Re-raise validation errors for proper API responses
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except OrchestrationError:
        # Re-raise orchestration errors
        raise
    except SQLAlchemyError as e:
        handle_db_error(e, "process_whatsapp_message", logger)
    except Exception as e:
        error_msg = f"Unexpected error in WhatsApp handler: {str(e)}"
        logger.exception(error_msg)
        raise OrchestrationError(
            error_msg,
            error_code=ErrorCode.ORCHESTRATION_ERROR,
            original_exception=e
        )


def broadcast_message(
    db: Session,
    content: str,
    instance_id: str,
    user_ids: List[str],
    trace_id: Optional[str] = None,
    parallel: bool = True
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
        trace_id: Trace ID for logging (optional)
        parallel: Whether to process broadcasts in parallel (default: True)
        
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
        channel="broadcast"
    )
    
    try:
        # Validate inputs before delegating
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
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
        
        # Log the request
        logger.info(f"Broadcasting message to {len(user_ids)} users")
        
        # Delegate to broadcast handler
        result = broadcast_message_internal(
            db=db,
            content=content,
            instance_id=instance_id,
            user_ids=user_ids,
            trace_id=trace_id,
            parallel=parallel
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
        
    except ValidationError:
        # Re-raise validation errors for proper API responses
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except SQLAlchemyError as e:
        handle_db_error(e, "broadcast_message", logger)
    except Exception as e:
        error_msg = f"Unexpected error in broadcast handler: {str(e)}"
        logger.exception(error_msg)
        # Consistent error code use - DATABASE_ERROR for database issues, INTERNAL_ERROR for other issues
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="broadcast_message"
        )