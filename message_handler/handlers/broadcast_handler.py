"""
Handler for message broadcasting.

This module provides functions for broadcasting messages to multiple users,
with support for parallel processing and error handling.
"""
import uuid
import time
import concurrent.futures
from typing import Dict, List, Any, Optional, Union, Tuple

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
MAX_PARALLEL_BROADCASTS = 10  # Maximum number of parallel broadcast operations
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
    Process broadcast to a single user with retry capability.
    
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
        
        # Use retry transaction for better reliability
        with retry_transaction(db, trace_id=trace_id, max_retries=2) as tx:
            # Get or create a session for this user
            session = get_or_create_session(tx, user_id, instance_id, trace_id=trace_id)
            if not session:
                logger.error("Failed to create or retrieve session")
                return {
                    "user_id": user_id,
                    "success": False,
                    "error": "Failed to create or retrieve session"
                }
            
            # Save the broadcast message
            message = save_broadcast_message(
                tx,
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
    trace_id: Optional[str] = None,
    parallel: bool = True
) -> Dict[str, Any]:
    """
    Broadcast a message to multiple users with parallel processing support.
    
    Args:
        db: Database session
        content: Message content
        instance_id: Instance ID
        user_ids: List of user IDs to send to
        trace_id: Trace ID for logging (optional)
        parallel: Whether to process broadcasts in parallel (default: True)
        
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
        instance_id=instance_id
    )
    
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
        
        # 3. Process broadcast to each user
        results = []
        
        if parallel and len(unique_user_ids) > 1:
            # Process in parallel using ThreadPoolExecutor
            logger.info(f"Processing broadcast in parallel for {len(unique_user_ids)} users")
            
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(MAX_PARALLEL_BROADCASTS, len(unique_user_ids))
            ) as executor:
                # Create a new database session for each thread
                futures = []
                
                for user_id in unique_user_ids:
                    if not user_id:
                        # Skip empty user IDs
                        continue
                    
                    # Create a unique trace ID for each user's message
                    user_trace_id = f"{trace_id}-{user_id}"
                    
                    # Submit task to executor
                    future = executor.submit(
                        process_broadcast_to_user,
                        db, user_id, instance_id, content, user_trace_id
                    )
                    futures.append(future)
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error in parallel broadcast task: {str(e)}")
                        # Add failure result
                        results.append({
                            "user_id": "unknown",  # Cannot determine which user failed
                            "success": False,
                            "error": f"Thread error: {str(e)}"
                        })
        else:
            # Process sequentially
            logger.info(f"Processing broadcast sequentially for {len(unique_user_ids)} users")
            
            for user_id in unique_user_ids:
                if not user_id:
                    # Skip empty user IDs
                    continue
                
                # Create a unique trace ID for each user's message
                user_trace_id = f"{trace_id}-{user_id}"
                
                # Process broadcast to this user
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
                "trace_id": trace_id
            }
        }
        
        return results_with_summary
        
    except ValidationError:
        # Re-raise validation errors
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except SQLAlchemyError as e:
        # Wrap database errors
        error_msg = f"Database error in broadcast: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="broadcast_message"
        )
    except Exception as e:
        # Wrap unexpected errors
        error_msg = f"Unexpected error in broadcast: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="broadcast_message"
        )