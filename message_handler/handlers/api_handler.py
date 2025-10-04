"""
Handler for API, web, and app message processing.

This module provides functions for processing messages from API, web,
and app channels, with support for idempotent processing and transaction
management.
"""
import uuid
import time
from typing import Dict, Any, Optional, List, Union

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError, 
    UnauthorizedError, DuplicateError, ErrorCode
)
from message_handler.services.idempotency_service import (
    create_idempotency_key, get_processed_message, 
    mark_message_processed, idempotency_lock
)
from message_handler.services.user_context_service import prepare_user_context
from message_handler.services.token_service import process_token_management
from message_handler.core.processor import process_core
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import transaction_scope, retry_transaction

# Constants
MAX_CONTENT_LENGTH = 10000
MAX_RETRY_ATTEMPTS = 3


def validate_message(
    content: str, 
    instance_id: str,
    trace_id: Optional[str] = None
) -> None:
    """
    Validate message content and instance ID.
    
    Args:
        content: Message content
        instance_id: Instance ID
        trace_id: Trace ID for logging (optional)
        
    Raises:
        ValidationError: If validation fails
    """
    logger = get_context_logger("api_handler", trace_id=trace_id)
    
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


def process_api_message(
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
    
    Handles the full lifecycle of a message, including validation, idempotency
    checking, user context preparation, token management, and core processing.
    
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
        UnauthorizedError: If user authentication fails
        DuplicateError: If concurrent request in progress
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "api_handler", 
        trace_id=trace_id,
        instance_id=instance_id,
        channel=channel
    )
    
    logger.info(f"Processing message through {channel} channel")
    
    try:
        # 1. Validate the message and instance
        validate_message(content, instance_id, trace_id)
        
        # 2. Create stable idempotency key if not provided
        if not idempotency_key:
            idempotency_key = create_idempotency_key(content, instance_id, user_details)
            logger.info(f"Generated idempotency key: {idempotency_key}")
        
        # 3. Check for duplicate message (idempotency)
        cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
        if cached_response:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return cached_response
        
        # 4. Process with idempotency lock
        with idempotency_lock(db, idempotency_key, trace_id=trace_id) as lock_result:
            # If lock_result is False, a cached result may now be available
            if lock_result is False:
                # Try to get the cached response again with retries
                for retry in range(MAX_RETRY_ATTEMPTS):
                    cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached_response:
                        logger.info(f"Found cached response after lock check (retry {retry})")
                        return cached_response
                    
                    # Short delay before retry
                    time.sleep(0.1 * (retry + 1))
                        
                logger.warning("Lock manager indicated cached result but none found after retries")
                # Continue with processing as fallback
            
            # 5. Process within a transaction with retry capability
            with transaction_scope(db, trace_id=trace_id) as tx:
                # Prepare user context
                user = prepare_user_context(tx, instance_id, user_details, channel, trace_id)
                
                # Process token management if session exists
                if user and hasattr(user, 'session') and user.session:
                    process_token_management(tx, user.session, trace_id)
                
                # Process the message
                result_data = process_core(
                    tx, 
                    content, 
                    instance_id, 
                    user=user,
                    user_details=user_details,
                    idempotency_key=idempotency_key,
                    trace_id=trace_id,
                    channel=channel
                )
                
                # Mark as processed for idempotency
                mark_message_processed(tx, idempotency_key, result_data, trace_id)
                
                processing_time = time.time() - start_time
                logger.info(f"Message processed successfully in {processing_time:.2f}s")
                
                # Add processing metadata to result
                if isinstance(result_data, dict) and "_meta" not in result_data:
                    result_data["_meta"] = {
                        "processing_time_seconds": round(processing_time, 3),
                        "trace_id": trace_id,
                        "channel": channel
                    }
                
                return result_data
                
    except ValidationError as e:
        # Log but re-raise validation errors
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError as e:
        # Log but re-raise resource not found errors
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except UnauthorizedError as e:
        # Log but re-raise unauthorized errors
        logger.warning(f"Unauthorized: {str(e)}")
        raise
    except DuplicateError as e:
        # Log but re-raise duplicate errors
        logger.warning(f"Duplicate request: {str(e)}")
        raise
    except SQLAlchemyError as e:
        # Wrap and log database errors
        error_msg = f"Database error processing message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="process_api_message"
        )
    except Exception as e:
        # Log and wrap unexpected errors
        error_msg = f"Unexpected error processing message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="process_api_message"
        )