"""
Idempotency service for message processing.

This module provides functions for ensuring idempotent processing of messages,
preventing duplicate processing of the same message.

IDEMPOTENCY SCOPING:
- Keys are scoped by INSTANCE (tenant boundary)
- Same request_id in different instances = different operations (both process)
- Same request_id in same instance = duplicate (returns cached response)

CACHE EXPIRY BEHAVIOR (Stripe-style):
- Cached responses are stored for 24 hours (configurable)
- Within 24 hours: Same request_id returns cached response (409)
- After 24 hours: request_id can be reused for NEW operation
- This matches industry standard (Stripe, AWS, Twilio)

EXAMPLE:
  Instance A, request_id="abc", 10:00 AM Day 1 → Process ✅ (msg-1)
  Instance A, request_id="abc", 11:00 AM Day 1 → 409 ❌ (cached from msg-1)
  Instance A, request_id="abc", 11:00 AM Day 2 → Process ✅ (msg-2, NEW!)
"""
import hashlib
import json
import uuid
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Generator, Union

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db.models.idempotency_locks import IdempotencyLockModel
from db.models.messages import MessageModel
from message_handler.exceptions import (
    DuplicateError, DatabaseError, ResourceNotFoundError,
    ValidationError, UnauthorizedError, ErrorCode
)
from message_handler.utils.logging import get_context_logger
from message_handler.utils.datetime_utils import get_current_datetime, ensure_timezone_aware

# Configuration
IDEMPOTENCY_CACHE_DURATION_MINUTES = 1440  # 24 hours
LOCK_EXPIRY_SECONDS = 300  # 5 minutes
MAX_RETRIES = 3
RETRY_DELAY_MS = 100
MAX_KEY_LENGTH = 128


def create_idempotency_key(
    request_id: str,
    instance_id: str,
    session_id: Optional[str] = None  # Backward compatible: Accept but ignore
) -> str:
    """
    Create an idempotency key scoped by instance.

    IMPORTANT: Keys are scoped by INSTANCE only, NOT by session.
    This ensures that the same request_id within the same instance is treated
    as a duplicate, regardless of which session it occurs in.

    Args:
        request_id: Client-provided request ID
        instance_id: Instance ID (tenant/bot identifier)
        session_id: [DEPRECATED] Session ID (ignored for backward compatibility)

    Returns:
        Scoped idempotency key (deterministic hash)

    Raises:
        ValidationError: If validation fails

    Example:
        create_idempotency_key("abc", "inst-A") → hash("inst-A:abc")
        create_idempotency_key("abc", "inst-B") → hash("inst-B:abc") (different!)
    """
    # Validation
    if not request_id or not isinstance(request_id, str) or not request_id.strip():
        raise ValidationError(
            "request_id is required and must be a non-empty string",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="request_id"
        )

    if len(request_id) > MAX_KEY_LENGTH:
        raise ValidationError(
            f"request_id exceeds maximum length of {MAX_KEY_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="request_id",
            details={"length": len(request_id), "max_length": MAX_KEY_LENGTH}
        )

    if not instance_id or not isinstance(instance_id, str) or not instance_id.strip():
        raise ValidationError(
            "instance_id is required and must be a non-empty string",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance_id"
        )

    # NOTE: session_id is accepted but IGNORED for production-grade idempotency
    # Keys are scoped by instance only, not by session

    # Create instance-scoped key
    scoped_key = f"{instance_id}:{request_id}"

    # Hash to fixed length for database storage
    key_hash = hashlib.sha256(scoped_key.encode()).hexdigest()[:32]

    return key_hash


def get_processed_message(
    db: Session,
    idempotency_key: str,
    max_age_minutes: int = IDEMPOTENCY_CACHE_DURATION_MINUTES,
    trace_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check if a message with this idempotency key has been processed recently.

    CACHE BEHAVIOR:
    - Returns cached response if message processed within max_age_minutes
    - Returns None if no message found OR message too old
    - After cache expiry, same idempotency_key can be reused (Stripe-style)

    Args:
        db: Database session
        idempotency_key: The idempotency key to check
        max_age_minutes: Maximum age for cached responses (default: 24 hours)
        trace_id: Trace ID for logging

    Returns:
        Cached response dict if found and recent, None otherwise
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)

    try:
        if not idempotency_key:
            logger.debug("No idempotency_key provided, skipping cache lookup")
            return None

        if not isinstance(idempotency_key, str):
            raise ValidationError(
                "idempotency_key must be a string",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="idempotency_key"
            )

        # Calculate cutoff time for cache
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

        # Query for recent processed messages only
        message = (db.query(MessageModel)
            .filter(
                MessageModel.request_id == idempotency_key,
                MessageModel.processed == True,
                MessageModel.created_at >= cutoff_time  # ← Only within cache window
            )
            .order_by(MessageModel.created_at.desc())
            .first())

        if not message:
            logger.debug("No recent processed message found - allowing processing")
            return None

        # Calculate age
        message_time = ensure_timezone_aware(message.created_at)
        now = get_current_datetime()
        age_minutes = (now - message_time).total_seconds() / 60

        # Extract cached response
        cached_response = None
        if hasattr(message, 'metadata_json') and message.metadata_json:
            if isinstance(message.metadata_json, dict):
                cached_response = message.metadata_json.get("cached_response")

        if cached_response:
            logger.info(
                f"Found cached response from {age_minutes:.1f} minutes ago "
                f"(expires in {max_age_minutes - age_minutes:.1f} minutes)"
            )
            return cached_response

        logger.warning(
            f"Message marked as processed but no cached response found "
            f"(age: {age_minutes:.1f} minutes)"
        )
        return None

    except SQLAlchemyError as e:
        error_msg = f"Database error checking for processed message: {str(e)}"
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
        error_msg = f"Unexpected error checking for processed message: {str(e)}"
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
    Mark a message as processed and cache the response.

    The cached response will be returned for duplicate requests within
    the cache duration (24 hours by default).

    Args:
        db: Database session
        idempotency_key: The idempotency key
        response_data: Response to cache
        trace_id: Trace ID for logging

    Returns:
        True if successful, False otherwise
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)

    try:
        if not idempotency_key:
            logger.warning("No idempotency_key provided, cannot mark as processed")
            return False

        if not isinstance(response_data, dict):
            raise ValidationError(
                "Response data must be a dictionary",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="response_data"
            )

        # Find the most recent message with this key
        message = (db.query(MessageModel)
            .filter(MessageModel.request_id == idempotency_key)
            .order_by(MessageModel.created_at.desc())
            .first())

        if not message:
            logger.warning(f"Message not found for idempotency_key: {idempotency_key}")
            return False

        # Sanitize and store response
        safe_response = _sanitize_response_data(response_data)
        message.processed = True

        # Merge with existing metadata
        if hasattr(message, 'metadata_json'):
            existing_meta = message.metadata_json if message.metadata_json else {}
            existing_meta.update({
                "processed_at": get_current_datetime().isoformat(),
                "cached_response": safe_response,
                "cache_expires_at": (
                    get_current_datetime() +
                    timedelta(minutes=IDEMPOTENCY_CACHE_DURATION_MINUTES)
                ).isoformat()
            })
            message.metadata_json = existing_meta

        db.flush()

        logger.info(
            f"Marked message {message.id} as processed with cached response "
            f"(expires in {IDEMPOTENCY_CACHE_DURATION_MINUTES} minutes)"
        )
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

    # Remove sensitive keys
    sensitive_keys = ["auth", "token", "secret", "password", "credential"]
    for key in list(result.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            result[key] = "********"

    # Truncate long strings
    for key, value in result.items():
        if isinstance(value, str) and len(value) > 1000:
            result[key] = value[:1000] + "... [truncated]"
        elif isinstance(value, dict):
            result[key] = _sanitize_response_data(value)

    # Check total size
    try:
        serialized = json.dumps(result)
        if len(serialized) > 65536:  # 64KB limit
            return {
                "text": result.get("text", "Response too large")[:1000],
                "status": result.get("status", "truncated"),
                "truncated": True
            }
    except (TypeError, ValueError):
        return {"error": "Cannot serialize response data", "truncated": True}

    return result


def _is_lock_orphaned(lock: Optional[IdempotencyLockModel]) -> bool:
    """Check if a lock is orphaned (older than expiry time)."""
    if not lock or not hasattr(lock, 'created_at') or lock.created_at is None:
        return True

    lock_time = ensure_timezone_aware(lock.created_at)
    now = get_current_datetime()
    age_seconds = (now - lock_time).total_seconds()

    return age_seconds > LOCK_EXPIRY_SECONDS


def _release_lock(db: Session, lock_id: Union[str, uuid.UUID], logger) -> bool:
    """Release a lock by ID."""
    if not lock_id:
        logger.warning("Invalid lock ID provided")
        return False

    try:
        result = db.query(IdempotencyLockModel).filter(
            IdempotencyLockModel.id == lock_id
        ).delete(synchronize_session=False)

        db.flush()

        if result > 0:
            logger.debug(f"Released lock ID {lock_id}")
            return True
        else:
            logger.debug(f"Lock ID {lock_id} not found (may have been released)")
            return False

    except Exception as e:
        logger.error(f"Error releasing lock {lock_id}: {str(e)}")
        return False


@contextmanager
def idempotency_lock(
    db: Session,
    idempotency_key: str,
    trace_id: Optional[str] = None,
    max_retries: int = MAX_RETRIES
) -> Generator[bool, None, None]:
    """
    Context manager for idempotency lock acquisition and release.

    Prevents concurrent processing of the same idempotency_key.
    Respects cache expiry - allows re-processing after cache expires.
    """
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)

    if not idempotency_key:
        logger.debug("No idempotency_key provided, skipping lock")
        yield True
        return

    lock_id = None

    try:
        # Calculate cache cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=IDEMPOTENCY_CACHE_DURATION_MINUTES)

        # Check if already processed recently (within cache window)
        processed_message = db.query(MessageModel).filter(
            MessageModel.request_id == idempotency_key,
            MessageModel.processed == True,
            MessageModel.created_at >= cutoff_time  # ← Respects cache expiry
        ).first()

        if processed_message:
            logger.info("Duplicate request detected - message already processed recently")
            raise DuplicateError(
                "Duplicate request. This message has already been processed.",
                error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                resource_type="message",
                resource_id=idempotency_key,
                details={
                    "idempotency_key": idempotency_key,
                    "message": "Response has been cached",
                    "retry_after_ms": 0
                }
            )

        # Check for existing locks
        existing_lock = db.query(IdempotencyLockModel).filter(
            IdempotencyLockModel.request_id == idempotency_key
        ).first()

        if existing_lock:
            if _is_lock_orphaned(existing_lock):
                logger.info(f"Found orphaned lock {existing_lock.id}, cleaning up")
                _release_lock(db, existing_lock.id, logger)
                db.commit()

                # Re-query to verify lock was released
                existing_lock = db.query(IdempotencyLockModel).filter(
                    IdempotencyLockModel.request_id == idempotency_key
                ).first()

                if existing_lock:
                    logger.warning(f"Lock still exists after cleanup attempt")
                    raise DuplicateError(
                        "Duplicate request. A request with this ID is already being processed.",
                        error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                        resource_type="message",
                        resource_id=idempotency_key,
                        details={
                            "idempotency_key": idempotency_key,
                            "message": "Please retry with exponential backoff",
                            "retry_after_ms": 1000
                        }
                    )
            else:
                logger.warning(f"Concurrent request detected: {idempotency_key}")
                raise DuplicateError(
                    "Duplicate request. A request with this ID is already being processed.",
                    error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                    resource_type="message",
                    resource_id=idempotency_key,
                    details={
                        "idempotency_key": idempotency_key,
                        "message": "Please retry with exponential backoff",
                        "retry_after_ms": 1000
                    }
                )

        # Try to acquire lock
        for attempt in range(1, max_retries + 1):
            try:
                lock_id = uuid.uuid4()
                new_lock = IdempotencyLockModel(
                    id=lock_id,
                    request_id=idempotency_key,
                    created_at=get_current_datetime()
                )

                db.add(new_lock)
                db.commit()

                logger.debug(f"Lock acquired with ID {lock_id}")
                break

            except IntegrityError:
                db.rollback()
                lock_id = None

                if attempt < max_retries:
                    # Check if message was processed during retry
                    cached = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached:
                        logger.info(f"Message processed during lock retry")
                        raise DuplicateError(
                            "Duplicate request. Message was processed during retry.",
                            error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                            resource_type="message",
                            resource_id=idempotency_key,
                            details={
                                "idempotency_key": idempotency_key,
                                "retry_after_ms": 0
                            }
                        )

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

        yield True

    finally:
        if lock_id:
            _release_lock(db, lock_id, logger)
