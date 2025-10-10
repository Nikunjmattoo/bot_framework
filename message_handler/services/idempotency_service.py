"""
Idempotency service for message processing.

This module provides functions for ensuring idempotent processing of messages,
preventing duplicate processing of the same message.
"""
import hashlib
import json
import uuid
import time
import random
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Generator, Union, List, cast

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import text

from db.models.idempotency_locks import IdempotencyLockModel
from db.models.messages import MessageModel
from message_handler.exceptions import (
    DuplicateError, DatabaseError, ResourceNotFoundError, 
    ValidationError, UnauthorizedError, ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction
from db.db import get_db
from message_handler.utils.datetime_utils import get_current_datetime, ensure_timezone_aware

# Constants
IDEMPOTENCY_CACHE_DURATION_MINUTES = 60  # Default cache duration
LOCK_EXPIRY_SECONDS = 300  # 5 minutes
MAX_RETRIES = 3
RETRY_DELAY_MS = 100
MAX_RETRY_DELAY_MS = 2000
MAX_KEY_LENGTH = 128  # Maximum length for idempotency keys

# Polling configuration for concurrent request handling
POLL_MAX_ATTEMPTS = 10  # Maximum number of polling attempts
POLL_INTERVAL_MS = 100  # Polling interval in milliseconds


def create_idempotency_key(
    content: str,
    instance_id: str,
    user_details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a stable idempotency key from message content and identifiers.
    
    Args:
        content: Message content
        instance_id: Instance ID
        user_details: User details (optional)
        
    Returns:
        Idempotency key string (SHA-256 hash)
        
    Raises:
        ValidationError: If input parameters are invalid
    """
    if not instance_id:
        raise ValidationError(
            "Instance ID is required for idempotency key generation",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )
    
    # Sanitize content if it's too large
    if len(content) > 10000:
        content = content[:10000]
    
    # Create a dictionary with the elements that determine uniqueness
    key_elements = {
        "content": content,
        "instance_id": str(instance_id)
    }
    
    # Add user details if available
    if user_details:
        for field in ["phone_e164", "email", "device_id", "phone", "whatsapp_message_id"]:
            if field in user_details and user_details[field]:
                key_elements[field] = str(user_details[field])
    
    # Convert to stable string and hash
    key_string = json.dumps(key_elements, sort_keys=True)
    hashed_key = hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    # Truncate if needed to meet DB constraints
    if len(hashed_key) > MAX_KEY_LENGTH:
        hashed_key = hashed_key[:MAX_KEY_LENGTH]
        
    return hashed_key


def get_processed_message(
    db: Session,
    idempotency_key: str,
    max_age_minutes: int = IDEMPOTENCY_CACHE_DURATION_MINUTES,
    trace_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check if a message with this idempotency key has already been processed.
    
    Args:
        db: Database session
        idempotency_key: Idempotency key to check
        max_age_minutes: Maximum age in minutes for cached responses (default: 60)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Cached response data or None if not found/expired
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)
    
    try:
        if not idempotency_key:
            logger.debug("No idempotency key provided, skipping cache lookup")
            return None
        
        if not isinstance(idempotency_key, str):
            raise ValidationError(
                "Idempotency key must be a string",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="idempotency_key"
            )
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        
        message = (db.query(MessageModel)
            .filter(
                MessageModel.idempotency_key == idempotency_key,
                MessageModel.processed == True,
                MessageModel.created_at >= cutoff_time
            )
            .order_by(MessageModel.created_at.desc())
            .first())
        
        if not message:
            logger.debug("No processed message found with given idempotency key")
            return None
        
        message_time = ensure_timezone_aware(message.created_at)
        now = get_current_datetime()
        age_minutes = (now - message_time).total_seconds() / 60
        
        # Check metadata_json first (preferred)
        cached_response = None
        if hasattr(message, 'metadata_json') and message.metadata_json:
            if isinstance(message.metadata_json, dict) and "cached_response" in message.metadata_json:
                cached_response = message.metadata_json["cached_response"]
        
        if cached_response:
            logger.info(f"Found cached response from {age_minutes:.1f} minutes ago")
            return cached_response
        
        logger.warning("Message marked as processed but no cached response found")
        return None
        
    except SQLAlchemyError as e:
        error_msg = f"Database error checking idempotency: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_processed_message"
        )
    except ValidationError:
        raise
    except Exception as e:
        error_msg = f"Unexpected error checking idempotency: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg, 
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_processed_message"
        )


def mark_message_processed(
    db: Session,
    idempotency_key: str,
    response_data: Dict[str, Any],
    trace_id: Optional[str] = None
) -> bool:
    """
    Mark a message as processed for idempotency and cache the response.
    
    Args:
        db: Database session
        idempotency_key: Idempotency key
        response_data: Response data to cache
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True on success, False if message not found
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)
    
    try:
        if not idempotency_key:
            logger.warning("No idempotency key provided, cannot mark as processed")
            return False
        
        if not isinstance(response_data, dict):
            raise ValidationError(
                "Response data must be a dictionary",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="response_data"
            )
        
        message = (db.query(MessageModel)
            .filter(MessageModel.idempotency_key == idempotency_key)
            .order_by(MessageModel.created_at.desc())
            .first())
            
        if not message:
            logger.warning("Message not found for idempotency key")
            return False
        
        safe_response = _sanitize_response_data(response_data)
        message.processed = True
        
        cache_data = {
            "processed_at": get_current_datetime().isoformat(),
            "cached_response": safe_response
        }
        
        # Only use metadata_json as the source of truth
        if hasattr(message, 'metadata_json'):
            message.metadata_json = cache_data
        
        db.flush()
        
        logger.info(f"Marked message {message.id} as processed with cached response")
        return True
        
    except SQLAlchemyError as e:
        error_msg = f"Database error marking message processed: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="mark_message_processed"
        )
    except ValidationError:
        raise
    except Exception as e:
        error_msg = f"Unexpected error marking message processed: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="mark_message_processed"
        )


def _sanitize_response_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize response data to remove sensitive information and limit size."""
    result = data.copy()
    
    sensitive_keys = ["auth", "token", "secret", "password", "credential"]
    for key in list(result.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            result[key] = "********"
    
    for key, value in result.items():
        if isinstance(value, str) and len(value) > 1000:
            result[key] = value[:1000] + "... [truncated]"
        elif isinstance(value, dict):
            result[key] = _sanitize_response_data(value)
    
    try:
        serialized = json.dumps(result)
        if len(serialized) > 65536:
            return {
                "text": result.get("text", "Response too large, truncated"),
                "status": result.get("status", "truncated"),
                "truncated": True
            }
    except (TypeError, ValueError):
        return {"error": "Cannot serialize response data", "truncated": True}
    
    return result


def _is_lock_orphaned(lock: Optional[IdempotencyLockModel]) -> bool:
    """Check if a lock is orphaned (older than the expiry time)."""
    if not lock or not hasattr(lock, 'created_at') or lock.created_at is None:
        return True
    
    lock_time = ensure_timezone_aware(lock.created_at)
    now = get_current_datetime()
    age_seconds = (now - lock_time).total_seconds()
    
    return age_seconds > LOCK_EXPIRY_SECONDS


def _release_lock(db: Session, lock_id: Union[str, uuid.UUID], logger) -> bool:
    """
    Release a lock by ID with immediate commit.
    
    Lock management is orthogonal to business transactions - locks must be
    released immediately to prevent blocking other requests.
    """
    if not lock_id:
        logger.warning("Invalid lock ID provided")
        return False
    
    try:
        result = db.query(IdempotencyLockModel).filter(
            IdempotencyLockModel.id == lock_id
        ).delete(synchronize_session=False)
        
        # CRITICAL: Commit immediately - locks are infrastructure, not business logic
        db.commit()
        
        if result > 0:
            logger.info(f"Released lock ID {lock_id}")
            return True
        else:
            logger.warning(f"Lock ID {lock_id} not found")
            return False
            
    except Exception as e:
        logger.error(f"Error releasing lock {lock_id}: {str(e)}")
        try:
            db.rollback()
        except:
            pass
        return False


def _poll_for_result(
    db: Session,
    idempotency_key: str,
    logger,
    max_attempts: int = POLL_MAX_ATTEMPTS,
    interval_ms: int = POLL_INTERVAL_MS
) -> Optional[Dict[str, Any]]:
    """
    Poll for a processed result from another concurrent request.
    
    This implements the enterprise pattern of waiting for the first request
    to complete rather than immediately failing with a conflict error.
    
    Args:
        db: Database session
        idempotency_key: The idempotency key to poll for
        logger: Logger instance
        max_attempts: Maximum number of polling attempts
        interval_ms: Interval between polls in milliseconds
        
    Returns:
        Cached response if found, None if timeout
    """
    logger.info(f"Polling for result from concurrent request (max {max_attempts} attempts)")
    
    for attempt in range(1, max_attempts + 1):
        # Check if the first request completed and cached its result
        cached_response = get_processed_message(db, idempotency_key)
        
        if cached_response:
            logger.info(f"Found cached result after {attempt} polling attempts")
            return cached_response
        
        # Check if lock still exists - if not, first request may have failed
        lock_exists = db.query(IdempotencyLockModel).filter(
            IdempotencyLockModel.idempotency_key == idempotency_key
        ).first()
        
        if not lock_exists and attempt > 1:
            # Lock released but no cached result - first request may have failed
            logger.warning("Lock released but no cached result found")
            break
        
        if attempt < max_attempts:
            logger.debug(f"Polling attempt {attempt}/{max_attempts}, waiting {interval_ms}ms")
            time.sleep(interval_ms / 1000)
    
    logger.warning(f"No result found after {max_attempts} polling attempts")
    return None


@contextmanager
def idempotency_lock(
    db: Session,
    idempotency_key: str,
    trace_id: Optional[str] = None,
    max_retries: int = MAX_RETRIES
) -> Generator[bool, None, None]:
    """
    Context manager for idempotency lock acquisition and release.
    
    Enterprise-grade implementation with polling for concurrent requests:
    - First request: Acquires lock and processes
    - Concurrent requests: Poll for first request's result (up to 1 second)
    - If polling times out: Raise 409 Conflict for client retry
    
    Yields:
        True if lock acquired successfully (new request)
        False if a processed result already exists (use cached result)
        
    Raises:
        DuplicateError: If concurrent request in progress and polling times out
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)
    
    if not idempotency_key:
        logger.debug("No idempotency key provided, skipping lock")
        yield True
        return
    
    lock_id = None
    
    try:
        # Check if already processed
        processed_message = db.query(MessageModel).filter(
            MessageModel.idempotency_key == idempotency_key,
            MessageModel.processed == True
        ).first()
        
        if processed_message:
            logger.info("Found processed message, returning cached result")
            yield False
            return
        
        # Check for existing locks and clean up orphaned ones
        existing_lock = db.query(IdempotencyLockModel).filter(
            IdempotencyLockModel.idempotency_key == idempotency_key
        ).first()
        
        if existing_lock:
            if _is_lock_orphaned(existing_lock):
                logger.info(f"Found orphaned lock {existing_lock.id}, cleaning up")
                _release_lock(db, existing_lock.id, logger)
            else:
                # ENTERPRISE PATTERN: Poll for result instead of immediate failure
                logger.info("Lock exists for key, polling for result from concurrent request")
                
                cached_result = _poll_for_result(
                    db, 
                    idempotency_key, 
                    logger,
                    max_attempts=POLL_MAX_ATTEMPTS,
                    interval_ms=POLL_INTERVAL_MS
                )
                
                if cached_result:
                    # Success! First request completed, return its cached result
                    logger.info("Retrieved result from concurrent request")
                    yield False
                    return
                
                # Polling timed out - first request still processing
                # Return 409 Conflict for client to retry
                logger.warning(f"Polling timed out, concurrent request still in progress")
                raise DuplicateError(
                    f"Request with idempotency key is being processed. Please retry in a moment.",
                    error_code=ErrorCode.DUPLICATE_IN_PROGRESS,
                    resource_type="message",
                    resource_id=idempotency_key,
                    details={
                        "idempotency_key": idempotency_key,
                        "retry_after_ms": 1000,
                        "reason": "concurrent_request_in_progress"
                    }
                )
        
        # Try to acquire lock with retries
        for attempt in range(1, max_retries + 1):
            try:
                lock_id = uuid.uuid4()
                new_lock = IdempotencyLockModel(
                    id=lock_id,
                    idempotency_key=idempotency_key,
                    created_at=get_current_datetime()
                )
                
                db.add(new_lock)
                db.commit()  # Commit lock acquisition immediately
                
                logger.info(f"Lock acquired with ID {lock_id}")
                break
                
            except IntegrityError:
                db.rollback()
                lock_id = None  # Clear since we didn't actually acquire it
                
                if attempt < max_retries:
                    # Check if result now available
                    cached = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached:
                        logger.info(f"Found cached result after lock retry")
                        yield False
                        return
                    
                    # Wait and retry
                    delay_ms = RETRY_DELAY_MS * (2 ** (attempt - 1))
                    logger.warning(f"Lock acquisition failed (attempt {attempt}/{max_retries}), retrying in {delay_ms}ms")
                    time.sleep(delay_ms / 1000)
                else:
                    raise DuplicateError(
                        f"Failed to acquire lock after {max_retries} attempts",
                        error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                        resource_type="message",
                        resource_id=idempotency_key
                    )
        
        # Lock acquired, do the work
        yield True
        
    finally:
        # Release lock if we acquired one
        if lock_id:
            _release_lock(db, lock_id, logger)