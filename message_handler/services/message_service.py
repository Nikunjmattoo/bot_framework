"""
Message service for creating and retrieving messages.

This module provides services for saving and retrieving different types of
messages including inbound user messages, outbound assistant messages,
and broadcast messages.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union
import uuid
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import text, desc
from sqlalchemy.exc import SQLAlchemyError

from db.models.messages import MessageModel
from db.models.sessions import SessionModel
from message_handler.exceptions import (
    ValidationError, DatabaseError, ResourceNotFoundError, 
    ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction

# Constants
MAX_MESSAGE_LENGTH = 10000  # Maximum message content length
MAX_METADATA_SIZE = 65536  # 64KB max metadata size

def save_inbound_message(
    db: Session,
    session_id: str,
    user_id: str,
    instance_id: str,
    content: str,
    channel: str = "api",
    meta_info: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    trace_id: Optional[str] = None
) -> MessageModel:
    """
    Save an inbound user message to the database.
    
    Args:
        db: Database session
        session_id: Session ID
        user_id: User ID
        instance_id: Instance ID
        content: Message content
        channel: Channel identifier (default: "api")
        meta_info: Additional metadata (optional)
        idempotency_key: Idempotency key (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Saved MessageModel instance
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
        # Validate inputs
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
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
        
        # Validate content length
        if content and len(content) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message content exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="content"
            )
        
        # Normalize content
        normalized_content = content.strip() if content else ""
        
        # Prepare metadata
        metadata = {
            "channel": channel,
        }
        
        # Add additional metadata if provided
        if meta_info:
            # Validate metadata size
            import json
            try:
                meta_json = json.dumps(meta_info)
                if len(meta_json) > MAX_METADATA_SIZE:
                    logger.warning(f"Meta info too large, truncating (size: {len(meta_json)} bytes)")
                    meta_info = {"truncated": True, "channel": channel}
            except (TypeError, ValueError):
                logger.warning("Invalid meta_info format, using default")
                meta_info = {"error": "invalid_format", "channel": channel}
                
            # Merge metadata
            metadata.update(meta_info)
        
        # Generate message ID
        message_id = uuid.uuid4()
        
        # Create message record
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=user_id,
            instance_id=instance_id,
            role="user",
            content=normalized_content,
            created_at=datetime.now(timezone.utc),
            meta_info=metadata,
            metadata_json=metadata,
            idempotency_key=idempotency_key,
            trace_id=trace_id
        )
        
        # Save to database
        db.add(message)
        db.flush()
        
        # Update session last activity time
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            session.last_message_at = datetime.now(timezone.utc)
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved inbound message: {message.id}")
        return message
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error saving inbound message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="save_inbound_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error saving inbound message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="save_inbound_message"
        )


def save_outbound_message(
    db: Session,
    session_id: str,
    instance_id: str,
    content: str,
    orchestrator_response: Optional[Dict[str, Any]] = None,
    channel: str = "api",
    meta_info: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> MessageModel:
    """
    Save an outbound assistant message to the database.
    
    Args:
        db: Database session
        session_id: Session ID
        instance_id: Instance ID
        content: Message content
        orchestrator_response: Full response from orchestrator (optional)
        channel: Channel identifier (default: "api")
        meta_info: Additional metadata (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Saved MessageModel instance
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
        # Validate inputs
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Validate content length
        if content and len(content) > MAX_MESSAGE_LENGTH:
            logger.warning(f"Message content exceeds maximum length, truncating (length: {len(content)} chars)")
            content = content[:MAX_MESSAGE_LENGTH] + "... [truncated]"
        
        # Normalize content
        normalized_content = content.strip() if content else ""
        
        # Prepare metadata
        metadata = {
            "channel": channel,
        }
        
        # Add additional metadata if provided
        if meta_info:
            # Validate and merge metadata
            try:
                import json
                meta_json = json.dumps(meta_info)
                if len(meta_json) > MAX_METADATA_SIZE:
                    logger.warning(f"Meta info too large, truncating (size: {len(meta_json)} bytes)")
                    meta_info = {"truncated": True, "channel": channel}
            except (TypeError, ValueError):
                logger.warning("Invalid meta_info format, using default")
                meta_info = {"error": "invalid_format", "channel": channel}
            
            metadata.update(meta_info)
        
        # Add orchestrator_response if provided (with size limit check)
        if orchestrator_response:
            try:
                import json
                orchestrator_json = json.dumps(orchestrator_response)
                if len(orchestrator_json) > MAX_METADATA_SIZE:
                    logger.warning(f"Orchestrator response too large, truncating (size: {len(orchestrator_json)} bytes)")
                    metadata["orchestrator_response"] = {"truncated": True}
                else:
                    metadata["orchestrator_response"] = orchestrator_response
            except (TypeError, ValueError):
                logger.warning("Invalid orchestrator_response format, skipping")
        
        # Generate message ID
        message_id = uuid.uuid4()
        
        # Create message record
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=None,  # Sent by system, not a user
            instance_id=instance_id,
            role="assistant",
            content=normalized_content,
            created_at=datetime.now(timezone.utc),
            meta_info=metadata,
            metadata_json=metadata,
            trace_id=trace_id
        )
        
        # Save to database
        db.add(message)
        db.flush()
        
        # Update session last activity time
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            session.last_message_at = datetime.now(timezone.utc)
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved outbound message: {message.id}")
        return message
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error saving outbound message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="save_outbound_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error saving outbound message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="save_outbound_message"
        )


def save_broadcast_message(
    db: Session,
    session_id: str,
    instance_id: str,
    content: str,
    trace_id: Optional[str] = None
) -> MessageModel:
    """
    Save a broadcast message to the database.
    
    Args:
        db: Database session
        session_id: Session ID
        instance_id: Instance ID
        content: Message content
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Saved MessageModel instance
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
        # Validate inputs
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Validate content length
        if content and len(content) > MAX_MESSAGE_LENGTH:
            logger.warning(f"Message content exceeds maximum length, truncating (length: {len(content)} chars)")
            content = content[:MAX_MESSAGE_LENGTH] + "... [truncated]"
        
        # Normalize content
        normalized_content = content.strip() if content else ""
        
        # Prepare metadata
        metadata = {"channel": "broadcast"}
        
        # Generate message ID
        message_id = uuid.uuid4()
        
        # Create message record
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=None,  # Sent by system, not a user
            instance_id=instance_id,
            role="assistant",
            content=normalized_content,
            created_at=datetime.now(timezone.utc),
            meta_info=metadata,
            metadata_json=metadata,
            trace_id=trace_id
        )
        
        # Save to database
        db.add(message)
        db.flush()
        
        # Update session last activity time
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            session.last_message_at = datetime.now(timezone.utc)
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved broadcast message: {message.id}")
        return message
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error saving broadcast message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="save_broadcast_message"
        )
    except Exception as e:
        error_msg = f"Unexpected error saving broadcast message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="save_broadcast_message"
        )


def get_recent_messages(
    db: Session,
    session_id: str,
    limit: int = 10,
    trace_id: Optional[str] = None
) -> List[MessageModel]:
    """
    Get recent messages for a session.
    
    Args:
        db: Database session
        session_id: Session ID
        limit: Maximum number of messages to retrieve
        trace_id: Trace ID for logging (optional)
        
    Returns:
        List of MessageModel instances ordered by created_at descending
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    try:
        # Validate inputs
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        if limit <= 0:
            raise ValidationError(
                "Limit must be a positive integer",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="limit"
            )
        
        # Cap limit at a reasonable value
        capped_limit = min(limit, 100)
        if capped_limit != limit:
            logger.warning(f"Limit capped at 100 (requested: {limit})")
        
        # Query for recent messages
        messages = (db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(desc(MessageModel.created_at))
            .limit(capped_limit)
            .all())
        
        logger.info(f"Retrieved {len(messages)} recent messages for session {session_id}")
        return messages
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error retrieving recent messages: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_recent_messages"
        )
    except Exception as e:
        error_msg = f"Unexpected error retrieving recent messages: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_recent_messages"
        )


def get_message_by_id(
    db: Session,
    message_id: str,
    trace_id: Optional[str] = None
) -> Optional[MessageModel]:
    """
    Get a message by ID.
    
    Args:
        db: Database session
        message_id: Message ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        MessageModel instance or None if not found
        
    Raises:
        ValidationError: If input validation fails
        DatabaseError: If database operation fails
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        message_id=message_id
    )
    
    try:
        # Validate inputs
        if not message_id:
            raise ValidationError(
                "Message ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="message_id"
            )
        
        # Query for the message
        message = (db.query(MessageModel)
            .filter(MessageModel.id == message_id)
            .first())
        
        if not message:
            logger.warning(f"Message not found: {message_id}")
            return None
        
        logger.debug(f"Retrieved message: {message_id}")
        return message
        
    except ValidationError:
        # Re-raise validation errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error retrieving message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_message_by_id"
        )
    except Exception as e:
        error_msg = f"Unexpected error retrieving message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_message_by_id"
        )