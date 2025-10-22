"""
Idempotency service for message processing.

This module provides functions for ensuring idempotent processing of messages,
preventing duplicate processing of the same message.

IDEMPOTENCY SCOPING:
- Keys are scoped by INSTANCE (tenant boundary)
- Same request_id in different instances = different operations (both process)
- Same request_id in same instance = duplicate (returns cached response)
- Session changes do NOT affect idempotency (sessions are ephemeral)
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

IDEMPOTENCY_CACHE_DURATION_MINUTES = 1440
LOCK_EXPIRY_SECONDS = 300
MAX_RETRIES = 3
RETRY_DELAY_MS = 100
MAX_RETRY_DELAY_MS = 2000
MAX_KEY_LENGTH = 128


def create_idempotency_key(
    request_id: str,
    instance_id: str
) -> str:
    """
    Create an idempotency key scoped by instance.
    
    IMPORTANT: Keys are scoped by INSTANCE only, NOT by session.
    This ensures that the same request_id within the same instance is treated
    as a duplicate, regardless of which session it occurs in.
    
    Args:
        request_id: Client-provided request ID
        instance_id: Instance ID (tenant/bot identifier)
        
    Returns:
        Scoped idempotency key (deterministic hash)
        
    Example:
        Instance A, request_id "abc" → hash("instance-a:abc")
        Instance B, request_id "abc" → hash("instance-b:abc") (different!)
        Instance A, session 1, request_id "abc" → hash("instance-a:abc")
        Instance A, session 2, request_id "abc" → hash("instance-a:abc") (same! = duplicate)
    """
    if not request_id:
        return None
    
    if not instance_id:
        # Fallback: if no instance_id, use raw request_id
        # This shouldn't happen in production
        return request_id
    
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
    """Check if a message with this idempotency key has already been processed."""
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
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        
        message = (db.query(MessageModel)
            .filter(
                MessageModel.request_id == idempotency_key,
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
    """Mark a message as processed for idempotency and cache the response."""
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
        
        message = (db.query(MessageModel)
            .filter(MessageModel.request_id == idempotency_key)
            .order_by(MessageModel.created_at.desc())
            .first())
            
        if not message:
            logger.warning("Message not found for idempotency_key")
            return False
        
        safe_response = _sanitize_response_data(response_data)
        message.processed = True
        
        # Merge with existing metadata instead of replacing
        if hasattr(message, 'metadata_json'):
            existing_meta = message.metadata_json if message.metadata_json else {}
            existing_meta.update({
                "processed_at": get_current_datetime().isoformat(),
                "cached_response": safe_response
            })
            message.metadata_json = existing_meta
        
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
            logger.info(f"Released lock ID {lock_id}")
            return True
        else:
            logger.warning(f"Lock ID {lock_id} not found")
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
    """Context manager for idempotency lock acquisition and release."""
    logger = get_context_logger("idempotency", trace_id=trace_id, idempotency_key=idempotency_key)
    
    if not idempotency_key:
        logger.debug("No idempotency_key provided, skipping lock")
        yield True
        return
    
    lock_id = None
    
    try:
        # Check if already processed
        processed_message = db.query(MessageModel).filter(
            MessageModel.request_id == idempotency_key,
            MessageModel.processed == True
        ).first()
        
        if processed_message:
            logger.info("Duplicate request detected - message already processed")
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
            else:
                logger.warning(f"Duplicate request detected: {idempotency_key}")
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
                
                logger.info(f"Lock acquired with ID {lock_id}")
                break
                
            except IntegrityError:
                db.rollback()
                lock_id = None
                
                if attempt < max_retries:
                    cached = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached:
                        logger.info(f"Found cached result after lock retry")
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