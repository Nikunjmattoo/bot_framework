"""
Handler for message broadcasting.

This module provides functions for broadcasting messages to multiple users,
with sequential processing to ensure transactional integrity.
"""
import uuid
import time
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError, 
    ErrorCode
)
from message_handler.services.instance_service import resolve_instance, get_instance_config
from message_handler.services.session_service import get_or_create_session
from message_handler.services.message_service import save_broadcast_message
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import transaction_scope, retry_transaction
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime

# Constants
MAX_CONTENT_LENGTH = 10000
MAX_BATCH_SIZE = 100  # Maximum number of users per batch


def validate_broadcast_parameters(
    content: str,
    instance_id: str,
    user_ids: List[str],
    trace_id: Optional[str] = None
) -> None:
    """
    Validate broadcast message parameters.
    
    Args:
        content: Message content
        instance_id: Instance ID
        user_ids: List of user IDs
        trace_id: Trace ID for logging (optional)
        
    Raises:
        ValidationError: If validation fails
    """
    logger = get_context_logger("broadcast_handler", trace_id=trace_id)
    
    # Validate content
    if not content or not content.strip():
        logger.warning("Message content cannot be empty")
        raise ValidationError(
            "Message content cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content"
        )
    
    # Check content length
    if len(content) > MAX_CONTENT_LENGTH:
        logger.warning(f"Message content exceeds maximum length: {len(content)} characters")
        raise ValidationError(
            f"Message content exceeds maximum length of {MAX_CONTENT_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content",
            details={"length": len(content), "max_length": MAX_CONTENT_LENGTH}
        )
    
    # Validate instance ID
    if not instance_id:
        logger.warning("Instance ID is required")
        raise ValidationError(
            "Instance ID is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )
    
    # Validate user IDs
    if not user_ids:
        logger.warning("No users provided for broadcast")
        raise ValidationError(
            "No users provided for broadcast",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="user_ids"
        )
    
    # Check batch size
    if len(user_ids) > MAX_BATCH_SIZE:
        logger.warning(f"Too many users in broadcast batch: {len(user_ids)}")
        raise ValidationError(
            f"Maximum batch size exceeded: {len(user_ids)} users (limit: {MAX_BATCH_SIZE})",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="user_ids",
            details={"count": len(user_ids), "limit": MAX_BATCH_SIZE}
        )


def process_broadcast_to_user(
    db: Session, 
    user_id: str, 
    instance_id: str, 
    content: str, 
    trace_id: str
) -> Dict[str, Any]:
    """
    Process broadcast to a single user.
    
    Args:
        db: Database session
        user_id: User ID
        instance_id: Instance ID
        content: Message content
        trace_id: Trace ID for logging
        
    Returns:
        Dict with broadcast result containing:
            - user_id: ID of the user
            - success: True if successful, False otherwise
            - message_id: ID of the broadcast message (if successful)
            - error: Error message (if failed)
    """
    logger = get_context_logger(
        "broadcast", 
        trace_id=trace_id,
        user_id=user_id,
        instance_id=instance_id
    )
    
    try:
        # Validate inputs
        if not user_id:
            return {
                "user_id": user_id,
                "success": False,
                "error": "User ID is required"
            }
            
        if not instance_id:
            return {
                "user_id": user_id,
                "success": False,
                "error": "Instance ID is required"
            }
        
        # Get or create a session for this user
        session = get_or_create_session(db, user_id, instance_id, trace_id=trace_id)
        if not session:
            logger.error("Failed to create or retrieve session")
            return {
                "user_id": user_id,
                "success": False,
                "error": "Failed to create or retrieve session"
            }
        
        # Save the broadcast message
        message = save_broadcast_message(
            db,
            session_id=str(session.id) if hasattr(session, 'id') else None,
            instance_id=instance_id,
            content=content,
            trace_id=trace_id
        )
        
        logger.info(f"Broadcast message sent to user {user_id}: {message.id if hasattr(message, 'id') else 'unknown'}")
        return {
            "user_id": user_id,
            "success": True,
            "message_id": str(message.id) if hasattr(message, 'id') else None,
            "session_id": str(session.id) if hasattr(session, 'id') else None
        }
        
    except Exception as e:
        logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
        return {
            "user_id": user_id,
            "success": False,
            "error": str(e)
        }


def broadcast_message_internal(
    db: Session,
    content: str,
    instance_id: str,
    user_ids: List[str],
    request_id: Optional[str] = None,  # ← ADD THIS LINE
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Broadcast a message to multiple users sequentially within a single transaction.
    
    This ensures atomicity - either all broadcasts succeed or all fail together.
    For async/parallel processing, use a message queue system (Celery, RabbitMQ, etc.).
    
    Args:
        db: Database session
        content: Message content
        instance_id: Instance ID
        user_ids: List of user IDs to send to
        request_id: Request ID for idempotency (optional)  # ← ADD THIS DOC
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Dict with broadcast results and summary information
        
    Raises:
        ValidationError: If message validation fails
        ResourceNotFoundError: If instance not found
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "broadcast_handler", 
        trace_id=trace_id,
        instance_id=instance_id,
        request_id=request_id  # ← ADD THIS TO LOGGER
    )
    
    # Rest of the function stays the same...
    # Deduplicate user IDs
    unique_user_ids = list(set(user_ids))
    if len(unique_user_ids) < len(user_ids):
        logger.info(f"Removed {len(user_ids) - len(unique_user_ids)} duplicate user IDs")
    
    logger.info(f"Broadcasting message to {len(unique_user_ids)} users")
    
    try:
        # 1. Validate inputs
        validate_broadcast_parameters(content, instance_id, unique_user_ids, trace_id)
        
        # 2. Verify instance and configuration
        instance = resolve_instance(db, instance_id)
        if not instance:
            logger.error(f"Instance not found: {instance_id}")
            raise ResourceNotFoundError(
                f"Instance not found: {instance_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance",
                resource_id=instance_id
            )
            
        instance_config = get_instance_config(db, instance_id)
        if not instance_config:
            logger.error(f"Configuration not found for instance: {instance_id}")
            raise ResourceNotFoundError(
                f"Configuration not found for instance: {instance_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance_config",
                resource_id=instance_id
            )
        
        # 3. Process broadcast to each user sequentially
        logger.info(f"Processing broadcast sequentially for {len(unique_user_ids)} users")
        
        results = []
        for user_id in unique_user_ids:
            if not user_id:
                continue
            
            user_trace_id = f"{trace_id}-{user_id}"
            result = process_broadcast_to_user(db, user_id, instance_id, content, user_trace_id)
            results.append(result)
        
        # Calculate statistics
        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful
        processing_time = time.time() - start_time
        
        logger.info(
            f"Broadcast completed in {processing_time:.2f}s: "
            f"{successful} successful, {failed} failed"
        )
        
        # Add summary statistics
        results_with_summary = {
            "results": results,
            "summary": {
                "total": len(results),
                "successful": successful,
                "failed": failed,
                "processing_time_seconds": round(processing_time, 3),
                "trace_id": trace_id,
                "request_id": request_id  # ← ADD THIS TO RESPONSE
            }
        }
        
        return results_with_summary
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError as e:
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error in broadcast: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="broadcast_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error in broadcast: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="broadcast_message"
        )