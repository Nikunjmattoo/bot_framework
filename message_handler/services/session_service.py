"""
Session management services.

This module provides functions for creating, retrieving, and managing
user sessions across different instances.
"""
from typing import Optional, Dict, Any, List, Union, Tuple, cast
from datetime import datetime, timedelta, timezone
import uuid
import os
import json

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text, desc

from db.models.sessions import SessionModel
from message_handler.exceptions import (
    DatabaseError, SessionManagementError, ValidationError,
    ResourceNotFoundError, ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction
from message_handler.utils.data_utils import sanitize_data
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime, update_session_timestamp

# Configuration (with environment variable fallbacks for flexibility)
DEFAULT_SESSION_TIMEOUT_MINUTES = int(os.environ.get("DEFAULT_SESSION_TIMEOUT_MINUTES", "60"))
MAX_SESSIONS_PER_USER = int(os.environ.get("MAX_SESSIONS_PER_USER", "10"))

# Use context logger for module-level logging
logger = get_context_logger("session_service")


def get_or_create_session(
    db: Session,
    user_id: str,
    instance_id: str,
    timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES,
    trace_id: Optional[str] = None
) -> Optional[SessionModel]:
    """
    Get an existing active session or create a new one.
    
    Args:
        db: Database session
        user_id: User ID
        instance_id: Instance ID
        timeout_minutes: Session timeout in minutes
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Active session
        
    Raises:
        ValidationError: If input validation fails
        SessionManagementError: If session creation or retrieval fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger("session_service", 
        trace_id=trace_id,
        user_id=user_id,
        instance_id=instance_id
    )
    
    try:
        # Validate inputs
        if not user_id:
            raise ValidationError(
                "User ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="user_id"
            )
        
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        if timeout_minutes <= 0:
            logger.warning(f"Invalid timeout_minutes ({timeout_minutes}), using default")
            timeout_minutes = DEFAULT_SESSION_TIMEOUT_MINUTES
        
        # Calculate session expiry threshold
        now = get_current_datetime()
        expiry_threshold = now - timedelta(minutes=timeout_minutes)
        
        # Find the most recent session for this user and instance
        session = (db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id, 
                SessionModel.instance_id == instance_id
            )
            .order_by(SessionModel.last_message_at.desc())
            .first())
        
        # If session exists and is active, return it
        if session:
            # Ensure last_message_at is timezone-aware
            last_message_at = session.last_message_at
            last_message_at = ensure_timezone_aware(last_message_at, field_name="session.last_message_at")
            
            # Check if session is expired
            if last_message_at < expiry_threshold:
                logger.info(f"Session {session.id} expired, creating a new one")
            else:
                logger.info(f"Using existing session: {session.id}")
                
                # Update session timestamp to keep it active
                session.last_message_at = now
                
                # Sanitize session metadata if it exists
                if hasattr(session, 'metadata_json') and isinstance(session.metadata_json, dict):
                    session.metadata_json = sanitize_data(
                        session.metadata_json,
                        strip_keys=["password", "token", "secret", "auth"],
                        max_string_length=1024
                    )
                    
                db.flush()
                
                return session
        
        # Try to create a new session using a retry transaction for reliability
        with retry_transaction(db, trace_id=trace_id) as tx:
            # Check if user has too many sessions
            active_sessions_count = (tx.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.last_message_at >= expiry_threshold
                )
                .count())
            
            if active_sessions_count >= MAX_SESSIONS_PER_USER:
                # Clean up oldest sessions if too many
                logger.warning(f"User {user_id} has too many active sessions, cleaning up oldest")
                
                # Find the oldest sessions to clean up
                old_sessions = (tx.query(SessionModel)
                    .filter(SessionModel.user_id == user_id)
                    .order_by(SessionModel.last_message_at.asc())
                    .limit(active_sessions_count - MAX_SESSIONS_PER_USER + 1)
                    .all())
                
                for old_session in old_sessions:
                    # Update the last_message_at field to mark it as inactive
                    old_session.last_message_at = expiry_threshold - timedelta(minutes=1)
                    
                    # If you need to track which sessions were cleaned up
                    if hasattr(old_session, 'metadata_json') and isinstance(old_session.metadata_json, dict):
                        # Sanitize metadata before adding cleanup info
                        old_session.metadata_json = sanitize_data(
                            old_session.metadata_json,
                            strip_keys=["password", "token", "secret", "auth"],
                            max_string_length=1024
                        )
                        old_session.metadata_json['cleaned_up'] = True
                        old_session.metadata_json['cleaned_at'] = now.isoformat()
               
                tx.flush()
            
            # Generate a unique session ID
            session_id = uuid.uuid4()
            
            # Create a new session
            new_session = SessionModel(
                id=session_id,
                user_id=user_id,
                instance_id=instance_id,
                created_at=now,
                last_message_at=now,
                token_plan_json=None  # Will be initialized by token service
            )

            new_session.initialize_default_state()

            tx.add(new_session)
            tx.flush()
            
            logger.info(f"Created new session: {new_session.id}")
            return new_session
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error in session management: {str(e)}"
        logger.error(error_msg)
        raise SessionManagementError(
            error_msg,
            error_code=ErrorCode.SESSION_ERROR,
            original_exception=e,
            session_id=str(session.id) if 'session' in locals() and session else None
        )
    except Exception as e:
        error_msg = f"Unexpected error in session management: {str(e)}"
        logger.exception(error_msg)
        raise SessionManagementError(
            error_msg,
            error_code=ErrorCode.SESSION_ERROR,
            original_exception=e,
            session_id=str(session.id) if 'session' in locals() and session else None
        )

def update_session_last_message(
    db: Session,
    session_id: str,
    trace_id: Optional[str] = None
) -> bool:
    """
    Update the last message timestamp for a session.
    
    Args:
        db: Database session
        session_id: Session ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True on success, False if session not found
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger("session_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    try:
        # Validate input
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        # Find the session
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            logger.warning(f"Session not found for update: {session_id}")
            return False
        
        # Update timestamp
        session = update_session_timestamp(session, field_name="last_message_at")
        
        # If session was expired, un-expire it
        if hasattr(session, 'expired') and session.expired:
            logger.info(f"Re-activating expired session: {session_id}")
            session.expired = False
            if hasattr(session, 'expired_at'):
                session.expired_at = None
        
        # Sanitize session metadata if it exists
        if hasattr(session, 'metadata_json') and isinstance(session.metadata_json, dict):
            session.metadata_json = sanitize_data(
                session.metadata_json,
                strip_keys=["password", "token", "secret", "auth"],
                max_string_length=1024
            )
                
        db.flush()
        
        logger.debug(f"Updated session last message time: {session_id}")
        return True
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error updating session: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="update_session_last_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error updating session: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="update_session_last_message"
        )


def expire_session(
    db: Session,
    session_id: str,
    trace_id: Optional[str] = None
) -> bool:
    """
    Expire a session.
    
    Args:
        db: Database session
        session_id: Session ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True on success, False if session not found
        
    Raises:
        ValidationError: If input validation fails
        ResourceNotFoundError: If session not found
        DatabaseError: If database operation fails
    """
    logger = get_context_logger("session_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    try:
        # Validate input
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        # Find the session
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            logger.warning(f"Session not found for expiry: {session_id}")
            raise ResourceNotFoundError(
                f"Session not found: {session_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="session",
                resource_id=session_id
            )
        
        # Mark as expired
        now = get_current_datetime()
        if hasattr(session, 'expired'):
            session.expired = True
        if hasattr(session, 'expired_at'):
            session.expired_at = now
        
        # Sanitize session metadata if it exists
        if hasattr(session, 'metadata_json') and isinstance(session.metadata_json, dict):
            session.metadata_json = sanitize_data(
                session.metadata_json,
                strip_keys=["password", "token", "secret", "auth"],
                max_string_length=1024
            )
            
        db.flush()
        
        logger.info(f"Expired session: {session_id}")
        return True
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error expiring session: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="expire_session"
        )
    except Exception as e:
        error_msg = f"Unexpected error expiring session: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="expire_session"
        )


def clean_expired_sessions(
    db: Session,
    older_than_days: int = 30,
    batch_size: int = 100,
    trace_id: Optional[str] = None
) -> int:
    """
    Clean up expired sessions older than specified days.
    
    Args:
        db: Database session
        older_than_days: Clean sessions older than this many days
        batch_size: Maximum number of sessions to clean in one batch
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Number of sessions cleaned up
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger("session_service", 
        trace_id=trace_id,
        older_than_days=older_than_days,
        batch_size=batch_size
    )
    
    try:
        # Validate inputs
        if older_than_days < 1:
            raise ValidationError(
                "older_than_days must be at least 1",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="older_than_days"
            )
        
        if batch_size < 1:
            raise ValidationError(
                "batch_size must be at least 1",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="batch_size"
            )
        
        # Calculate cutoff date
        now = get_current_datetime()
        cutoff_date = now - timedelta(days=older_than_days)
        
        # Find sessions to clean - sessions with old last_message_at
        expired_sessions = (db.query(SessionModel)
            .filter(
                SessionModel.last_message_at < cutoff_date  # ← FIXED: Use existing field
            )
            .limit(batch_size)
            .all())
        
        if not expired_sessions:
            logger.info(f"No expired sessions older than {older_than_days} days found")
            return 0
        
        # Get IDs for logging
        session_ids = [str(session.id) if hasattr(session, 'id') else "unknown" for session in expired_sessions]
        
        # Delete the sessions
        for session in expired_sessions:
            db.delete(session)
        
        db.flush()
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        return len(expired_sessions)
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error cleaning expired sessions: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="clean_expired_sessions"
        )
    except Exception as e:
        error_msg = f"Unexpected error cleaning expired sessions: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="clean_expired_sessions"
        )

def get_session_info(
    db: Session,
    session_id: str,
    trace_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a session.
    
    Args:
        db: Database session
        session_id: Session ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Dictionary with session information or None if not found
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger("session_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    try:
        # Validate input
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        # Find the session with related data
        session = (db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first())
        
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        # Calculate session age and activity status
        now = get_current_datetime()
        
        # Ensure created_at and last_message_at are timezone-aware
        created_at = session.created_at if hasattr(session, 'created_at') else now
        created_at = ensure_timezone_aware(created_at, field_name="session.created_at")
            
        last_message_at = session.last_message_at if hasattr(session, 'last_message_at') else now
        last_message_at = ensure_timezone_aware(last_message_at, field_name="session.last_message_at")
        
        session_age = (now - created_at).total_seconds() / 60  # in minutes
        inactive_time = (now - last_message_at).total_seconds() / 60  # in minutes
        
        # Build the session info
        session_info = {
            "id": str(session.id) if hasattr(session, 'id') else None,
            "user_id": str(session.user_id) if hasattr(session, 'user_id') else None,
            "instance_id": str(session.instance_id) if hasattr(session, 'instance_id') else None,
            "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else None,
            "last_message_at": last_message_at.isoformat() if hasattr(last_message_at, 'isoformat') else None,
            "age_minutes": round(session_age, 1),
            "inactive_minutes": round(inactive_time, 1),
            "expired": session.expired if hasattr(session, 'expired') else False,
            "has_token_plan": hasattr(session, 'token_plan_json') and session.token_plan_json is not None,
        }
        
        # Count messages in session
        try:
            message_count_query = text("""
                SELECT role, COUNT(*) as count
                FROM messages
                WHERE session_id = :session_id
                GROUP BY role
            """)
            
            message_counts = db.execute(message_count_query, {"session_id": session_id}).fetchall()
            
            message_stats = {
                "total": 0
            }
            
            for role, count in message_counts:
                message_stats[role] = count
                message_stats["total"] += count
            
            session_info["message_counts"] = message_stats
        except Exception as e:
            logger.warning(f"Error fetching message counts: {str(e)}")
            session_info["message_counts"] = {"total": 0, "error": str(e)}
        
        logger.info(f"Retrieved session info for: {session_id}")
        return session_info
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error retrieving session info: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_session_info"
        )
    except Exception as e:
        error_msg = f"Unexpected error retrieving session info: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_session_info"
        )