"""
Message service for creating and retrieving messages.

This module provides services for saving and retrieving different types of
messages including inbound user messages, outbound assistant messages,
and broadcast messages.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union
import uuid
import json
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


def _validate_content_length(content: str, field_name: str = "content") -> str:
    """
    Validate and normalize message content length.
    
    Args:
        content: Message content
        field_name: Field name for validation errors
        
    Returns:
        Normalized content string
        
    Raises:
        ValidationError: If content length exceeds maximum
    """
    # Normalize content
    normalized_content = content.strip() if content else ""
    
    # Validate length
    if len(normalized_content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f"Message content exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field=field_name,
            details={"length": len(normalized_content), "max_length": MAX_MESSAGE_LENGTH}
        )
    
    return normalized_content


def _validate_metadata_size(meta_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate metadata size and truncate if needed.
    
    Args:
        meta_info: Metadata to validate
        
    Returns:
        Validated (and possibly truncated) metadata
    """
    if not meta_info:
        return {}
    
    # Try to serialize and check size
    try:
        meta_json = json.dumps(meta_info)
        if len(meta_json) > MAX_METADATA_SIZE:
            # Truncate metadata if too large
            truncated_meta = {"truncated": True}
            
            # Preserve essential fields if possible
            for key in ["channel", "whatsapp_message_id", "message_type"]:
                if key in meta_info:
                    truncated_meta[key] = meta_info[key]
            
            return truncated_meta
    except (TypeError, ValueError):
        # If serialization fails, return minimal metadata
        return {"error": "invalid_format"}
    
    return meta_info


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
        
        # Validate and normalize content
        normalized_content = _validate_content_length(content)
        
        # Prepare metadata
        metadata = {
            "channel": channel,
        }
        
        # Add additional metadata if provided
        if meta_info:
            # Validate metadata size
            validated_meta = _validate_metadata_size(meta_info)
            
            # Merge metadata
            metadata.update(validated_meta)
        
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
        handle_db_error(e, "save_inbound_message", logger)
    except Exception as e:
        handle_db_error(e, "save_inbound_message", logger, ErrorCode.INTERNAL_ERROR)


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
        
        # Validate and normalize content (truncate if necessary)
        normalized_content = ""
        try:
            normalized_content = _validate_content_length(content)
        except ValidationError as e:
            logger.warning(f"Content too long, truncating: {str(e)}")
            normalized_content = content[:MAX_MESSAGE_LENGTH] + "... [truncated]"
        
        # Prepare metadata
        metadata = {
            "channel": channel,
        }
        
        # Add additional metadata if provided
        if meta_info:
            # Validate metadata size
            validated_meta = _validate_metadata_size(meta_info)
            
            # Merge metadata
            metadata.update(validated_meta)
        
        # Add orchestrator_response if provided (with size limit check)
        if orchestrator_response:
            # Validate and possibly truncate orchestrator response
            try:
                import json
                orchestrator_json = json.dumps(orchestrator_response)
                if len(orchestrator_json) > MAX_METADATA_SIZE:
                    logger.warning(f"Orchestrator response too large, truncating (size: {len(orchestrator_json)} bytes)")
                    metadata["orchestrator_response"] = {
                        "truncated": True,
                        "text": orchestrator_response.get("text", "")[:1000] + "..." if orchestrator_response.get("text") else None
                    }
                else:
                    metadata["orchestrator_response"] = orchestrator_response
            except (TypeError, ValueError):
                logger.warning("Invalid orchestrator_response format, skipping")
                metadata["orchestrator_response_error"] = "invalid_format"
        
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
        handle_db_error(e, "save_outbound_message", logger)
    except Exception as e:
        handle_db_error(e, "save_outbound_message", logger, ErrorCode.INTERNAL_ERROR)


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
        
        # Validate and normalize content (truncate if necessary)
        normalized_content = ""
        try:
            normalized_content = _validate_content_length(content)
        except ValidationError as e:
            logger.warning(f"Content too long, truncating: {str(e)}")
            normalized_content = content[:MAX_MESSAGE_LENGTH] + "... [truncated]"
        
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
        handle_db_error(e, "save_broadcast_message", logger)
    except Exception as e:
        handle_db_error(e, "save_broadcast_message", logger, ErrorCode.INTERNAL_ERROR)


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
        ResourceNotFoundError: If session not found
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
        
        # Validate session exists
        session_exists = db.query(SessionModel).filter(SessionModel.id == session_id).first() is not None
        if not session_exists:
            raise ResourceNotFoundError(
                f"Session not found: {session_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="session",
                resource_id=session_id
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
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except SQLAlchemyError as e:
        handle_db_error(e, "get_recent_messages", logger)
    except Exception as e:
        handle_db_error(e, "get_recent_messages", logger, ErrorCode.INTERNAL_ERROR)


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
        handle_db_error(e, "get_message_by_id", logger)
    except Exception as e:
        handle_db_error(e, "get_message_by_id", logger, ErrorCode.INTERNAL_ERROR)