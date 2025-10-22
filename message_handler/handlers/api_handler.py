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
    create_idempotency_key,
    get_processed_message, 
    mark_message_processed, 
    idempotency_lock
)
from message_handler.services.user_context_service import prepare_user_context
from message_handler.services.token_service import TokenManager
from message_handler.core.processor import process_core
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import transaction_scope, retry_transaction

MAX_CONTENT_LENGTH = 10000
MAX_RETRY_ATTEMPTS = 3


def validate_message(
    content: str, 
    instance_id: str,
    trace_id: Optional[str] = None
) -> None:
    """Validate message content and instance ID."""
    logger = get_context_logger("api_handler", trace_id=trace_id)
    
    if not content or not content.strip():
        logger.warning("Message content cannot be empty")
        raise ValidationError(
            "Message content cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content"
        )
    
    if len(content) > MAX_CONTENT_LENGTH:
        logger.warning(f"Message content exceeds maximum length: {len(content)} characters")
        raise ValidationError(
            f"Message content exceeds maximum length of {MAX_CONTENT_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content",
            details={"length": len(content), "max_length": MAX_CONTENT_LENGTH}
        )
    
    if not instance_id:
        logger.warning("Instance ID is required")
        raise ValidationError(
            "Instance ID is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )
    
    # Validate UUID format
    try:
        uuid.UUID(instance_id)
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"Invalid instance_id format: {instance_id}")
        raise ValidationError(
            "Invalid instance_id format: must be a valid UUID",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id",
            value=instance_id
        )


def process_api_message(
    db: Session,
    content: str,
    instance_id: str,
    user_details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    channel: str = "api"
) -> Dict[str, Any]:
    """
    Process an incoming message from API/web/app channels.
    
    Uses instance-scoped idempotency keys to prevent duplicates within the same instance.
    """
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "api_handler", 
        trace_id=trace_id,
        instance_id=instance_id,
        channel=channel,
        request_id=request_id
    )
    
    logger.info(f"Processing message through {channel} channel")
    
    try:
        validate_message(content, instance_id, trace_id)
        
        # Create instance-scoped idempotency key
        idempotency_key = create_idempotency_key(
            request_id=request_id,
            instance_id=instance_id
        )
        logger.info(f"Created idempotency key (instance-scoped)")
        
        # Check for duplicate BEFORE creating user/session
        cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
        if cached_response:
            logger.info(f"Duplicate request detected for idempotency_key")
            raise DuplicateError(
                "Duplicate request - response already processed",
                error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                request_id=request_id,
                details={"request_id": request_id, "cached_response": cached_response}
            )
        
        # Create user context (after duplicate check)
        user = prepare_user_context(db, instance_id, user_details, channel, trace_id)
        
        # Acquire lock with idempotency key
        with idempotency_lock(db, idempotency_key, trace_id=trace_id) as lock_result:
            if lock_result is False:
                # Try to get the cached response again with retries
                for retry in range(MAX_RETRY_ATTEMPTS):
                    cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached_response:
                        logger.info(f"Duplicate request after lock check (retry {retry})")
                        raise DuplicateError(
                            "Duplicate request - response already processed",
                            error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                            request_id=request_id,
                            details={"request_id": request_id, "cached_response": cached_response}
                        )
                    
                    time.sleep(0.1 * (retry + 1))
                        
                logger.warning("Lock manager indicated cached result but none found after retries")
            
            with transaction_scope(db, trace_id=trace_id) as tx:
                if user and hasattr(user, 'session') and user.session:
                    try:
                        token_manager = TokenManager()
                        token_manager.initialize_session(tx, str(user.session.id), trace_id)
                        logger.debug("Token plan initialized for session")
                    except Exception as e:
                        logger.warning(f"Error initializing token plan: {str(e)}")
                
                # Pass idempotency key for database storage, original request_id in metadata
                result_data = process_core(
                    tx,
                    content,
                    instance_id,
                    user=user,
                    user_details=user_details,
                    request_id=idempotency_key,  # Hashed key for DB request_id field
                    trace_id=trace_id,
                    channel=channel,
                    meta_info={"request_id": request_id}  # Original request_id for metadata
                )
                
                # Mark as processed with idempotency key
                mark_message_processed(tx, idempotency_key, result_data, trace_id)
                
                processing_time = time.time() - start_time
                logger.info(f"Message processed successfully in {processing_time:.2f}s")
                
                if isinstance(result_data, dict) and "_meta" not in result_data:
                    result_data["_meta"] = {
                        "processing_time_seconds": round(processing_time, 3),
                        "trace_id": trace_id,
                        "channel": channel,
                        "request_id": request_id
                    }
                
                return result_data
                
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError as e:
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except UnauthorizedError as e:
        logger.warning(f"Unauthorized: {str(e)}")
        raise
    except DuplicateError as e:
        logger.warning(f"Duplicate request: {str(e)}")
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error processing message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="process_api_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error processing message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="process_api_message"
        )