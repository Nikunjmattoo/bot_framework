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
from message_handler.utils.validation import validate_metadata_field_size
from message_handler.utils.error_handling import handle_database_error
from message_handler.utils.data_utils import sanitize_data
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime


# Constants
MAX_MESSAGE_LENGTH = 10000
MAX_METADATA_SIZE = 65536


def _validate_content_length(content: str, field_name: str = "content") -> str:
    """Validate and normalize message content length."""
    normalized_content = content.strip() if content else ""
    
    if len(normalized_content) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f"Message content exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field=field_name,
            details={"length": len(normalized_content), "max_length": MAX_MESSAGE_LENGTH}
        )
    
    return normalized_content


def _validate_metadata_size(meta_info: Dict[str, Any]) -> Dict[str, Any]:
    """Validate metadata size and truncate if needed."""
    is_valid, _, normalized_meta = validate_metadata_field_size(meta_info)
    return normalized_meta


def save_inbound_message(
    db: Session,
    session_id: str,
    user_id: str,
    instance_id: str,
    content: str,
    channel: str = "api",
    meta_info: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
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
        request_id: Request ID for idempotency (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Saved MessageModel instance
    """
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
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
        
        normalized_content = _validate_content_length(content)
        
        sanitized_meta = sanitize_data(
            meta_info or {},
            strip_keys=["password", "token", "secret", "auth"],
            max_string_length=1024
        )
        
        metadata = {"channel": channel}
        
        if sanitized_meta:
            validated_meta = _validate_metadata_size(sanitized_meta)
            metadata.update(validated_meta)
        
        message_id = uuid.uuid4()
        
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=user_id,
            instance_id=instance_id,
            role="user",
            content=normalized_content,
            created_at=get_current_datetime(),
            metadata_json=metadata,
            request_id=request_id,
            trace_id=trace_id
        )
        
        db.add(message)
        db.flush()
        
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            session.last_message_at = get_current_datetime()
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved inbound message: {message.id}")
        return message
        
    except ValidationError:
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "save_inbound_message", logger, trace_id=trace_id)
    except Exception as e:
        handle_database_error(e, "save_inbound_message", logger, error_code=ErrorCode.INTERNAL_ERROR)


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
    """Save an outbound assistant message to the database."""
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
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
        
        normalized_content = ""
        try:
            normalized_content = _validate_content_length(content)
        except ValidationError as e:
            logger.warning(f"Content too long, truncating: {str(e)}")
            suffix = "... [truncated]"
            truncate_at = MAX_MESSAGE_LENGTH - len(suffix)
            normalized_content = content[:truncate_at] + suffix
        
        sanitized_meta = sanitize_data(
            meta_info or {},
            strip_keys=["password", "token", "secret", "auth"],
            max_string_length=1024
        )
        
        sanitized_orchestrator = sanitize_data(
            orchestrator_response or {},
            max_string_length=10000,
            max_dict_items=100
        )
        
        metadata = {"channel": channel}
        
        if sanitized_meta:
            validated_meta = _validate_metadata_size(sanitized_meta)
            metadata.update(validated_meta)
        
        if sanitized_orchestrator:
            try:
                orchestrator_json = json.dumps(sanitized_orchestrator)
                if len(orchestrator_json) > MAX_METADATA_SIZE:
                    logger.warning(f"Orchestrator response too large, truncating (size: {len(orchestrator_json)} bytes)")
                    metadata["orchestrator_response"] = {
                        "truncated": True,
                        "text": sanitized_orchestrator.get("text", "")[:1000] + "..." if sanitized_orchestrator.get("text") else None
                    }
                else:
                    metadata["orchestrator_response"] = sanitized_orchestrator
            except (TypeError, ValueError):
                logger.warning("Invalid orchestrator_response format, skipping")
                metadata["orchestrator_response_error"] = "invalid_format"
        
        message_id = uuid.uuid4()
        
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=None,
            instance_id=instance_id,
            role="assistant",
            content=normalized_content,
            created_at=get_current_datetime(),
            metadata_json=metadata,
            trace_id=trace_id
        )
        
        db.add(message)
        db.flush()
        
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            current_time = get_current_datetime()
            session.last_message_at = current_time
            session.last_assistant_message_at = current_time
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved outbound message: {message.id}")
        return message
        
    except ValidationError:
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "save_outbound_message", logger)
    except Exception as e:
        handle_database_error(e, "save_outbound_message", logger, ErrorCode.INTERNAL_ERROR)


def save_broadcast_message(
    db: Session,
    session_id: str,
    instance_id: str,
    content: str,
    trace_id: Optional[str] = None
) -> MessageModel:
    """Save a broadcast message to the database."""
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id,
        instance_id=instance_id
    )
    
    try:
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
        
        normalized_content = ""
        try:
            normalized_content = _validate_content_length(content)
        except ValidationError as e:
            logger.warning(f"Content too long, truncating: {str(e)}")
            suffix = "... [truncated]"
            truncate_at = MAX_MESSAGE_LENGTH - len(suffix)
            normalized_content = content[:truncate_at] + suffix

        metadata = {"channel": "broadcast"}
        message_id = uuid.uuid4()
        
        message = MessageModel(
            id=message_id,
            session_id=session_id,
            user_id=None,
            instance_id=instance_id,
            role="assistant",
            content=normalized_content,
            created_at=get_current_datetime(),
            metadata_json=metadata,
            trace_id=trace_id
        )
        
        db.add(message)
        db.flush()
        
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            session.last_message_at = get_current_datetime()
            db.flush()
        else:
            logger.warning(f"Session not found for update: {session_id}")
        
        logger.info(f"Saved broadcast message: {message.id}")
        return message
        
    except ValidationError:
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "save_broadcast_message", logger, trace_id=trace_id)
    except Exception as e:
        handle_database_error(e, "save_broadcast_message", logger, error_code=ErrorCode.INTERNAL_ERROR)


def get_recent_messages(
    db: Session,
    session_id: str,
    limit: int = 10,
    trace_id: Optional[str] = None
) -> List[MessageModel]:
    """Get recent messages for a session."""
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    try:
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
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
        
        capped_limit = min(limit, 100)
        if capped_limit != limit:
            logger.warning(f"Limit capped at 100 (requested: {limit})")
        
        messages = (db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(desc(MessageModel.created_at))
            .limit(capped_limit)
            .all())
        
        logger.info(f"Retrieved {len(messages)} recent messages for session {session_id}")
        return messages
        
    except ValidationError:
        raise
    except ResourceNotFoundError:
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "get_recent_messages", logger, trace_id=trace_id)
    except Exception as e:
        handle_database_error(e, "get_recent_messages", logger, error_code=ErrorCode.INTERNAL_ERROR)


def get_message_by_id(
    db: Session,
    message_id: str,
    trace_id: Optional[str] = None
) -> Optional[MessageModel]:
    """Get a message by ID."""
    logger = get_context_logger(
        "message_service", 
        trace_id=trace_id,
        message_id=message_id
    )
    
    try:
        if not message_id:
            raise ValidationError(
                "Message ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="message_id"
            )
        
        message = (db.query(MessageModel)
            .filter(MessageModel.id == message_id)
            .first())
        
        if not message:
            logger.warning(f"Message not found: {message_id}")
            return None
        
        logger.debug(f"Retrieved message: {message_id}")
        return message
        
    except ValidationError:
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "get_message_by_id", logger, trace_id=trace_id)
    except Exception as e:
        handle_database_error(e, "get_message_by_id", logger, error_code=ErrorCode.INTERNAL_ERROR)