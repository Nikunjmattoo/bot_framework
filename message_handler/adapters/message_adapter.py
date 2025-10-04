"""
Message adapter builder for orchestrator.

This module provides functions to build the message adapter
for communication with the conversation orchestrator.
"""
from typing import Dict, Any, Optional, Union, List, cast
from sqlalchemy.orm import Session
import json
import uuid
import time

from message_handler.services.token_service import get_token_budgets
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.exceptions import ValidationError, ErrorCode
from message_handler.utils.validation import validate_metadata_field_size
from message_handler.utils.data_utils import sanitize_data

# Constants
DEFAULT_CHANNEL = "api"
MAX_ADAPTER_SIZE = 1048576  # 1MB maximum adapter size


def sanitize_adapter(adapter: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize adapter to remove sensitive information and limit size.
    
    Args:
        adapter: Original adapter dictionary
        
    Returns:
        Sanitized adapter
    """
    return sanitize_data(
        adapter,
        strip_keys=["password", "token", "credential", "secret", "auth"],
        max_string_length=10000,
        max_dict_items=100
    )


def validate_adapter(
    adapter: Dict[str, Any], 
    trace_id: Optional[str] = None
) -> None:
    """
    Validate adapter structure and content.
    
    Args:
        adapter: Adapter dictionary
        trace_id: Trace ID for logging (optional)
        
    Raises:
        ValidationError: If validation fails
    """
    logger = get_context_logger("message_adapter", trace_id=trace_id)
    
    # Required fields
    required_fields = ["session_id", "user_id", "message", "routing"]
    
    # Check for missing required fields
    missing_fields = [field for field in required_fields if field not in adapter]
    if missing_fields:
        error_msg = f"Missing required fields in adapter: {', '.join(missing_fields)}"
        logger.warning(error_msg)
        raise ValidationError(
            error_msg,
            error_code=ErrorCode.VALIDATION_ERROR,
            field="adapter",
            details={"missing_fields": missing_fields}
        )
    
    # Validate message field
    message = adapter.get("message", {})
    if not isinstance(message, dict):
        logger.warning("Message field must be a dictionary")
        raise ValidationError(
            "Message field must be a dictionary",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="message",
            details={"actual_type": type(message).__name__}
        )
    
    if "content" not in message:
        logger.warning("Message must contain content field")
        raise ValidationError(
            "Message must contain content field",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="message.content"
        )
    
    # Validate routing field
    routing = adapter.get("routing", {})
    if not isinstance(routing, dict):
        logger.warning("Routing field must be a dictionary")
        raise ValidationError(
            "Routing field must be a dictionary",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing",
            details={"actual_type": type(routing).__name__}
        )
    
    if "instance_id" not in routing:
        logger.warning("Routing must contain instance_id field")
        raise ValidationError(
            "Routing must contain instance_id field",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing.instance_id"
        )
    
    # Check total adapter size using validate_metadata_size
    is_valid, error_msg, _ = validate_metadata_field_size(
        adapter, 
        max_size_kb=1024,  # 1MB limit
        field_name="adapter"
    )
    
    if not is_valid:
        logger.warning(error_msg)
        raise ValidationError(
            error_msg,
            error_code=ErrorCode.VALIDATION_ERROR,
            field="adapter"
        )


def build_message_adapter(
    session: Any, 
    user: Any, 
    instance: Any, 
    instance_config: Any, 
    message: Any, 
    trace_id: Optional[str] = None, 
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Build a message adapter for the orchestrator.
    
    Args:
        session: SessionModel instance
        user: UserModel instance
        instance: InstanceModel instance
        instance_config: InstanceConfigModel instance
        message: MessageModel instance
        trace_id: Trace ID for logging (optional)
        db: Database session (optional, needed for token management)
        
    Returns:
        dict: Message adapter for orchestrator with the following structure:
            - session_id: Session ID
            - session_context: Session context information
            - user_id: User ID
            - is_guest: Whether the user is a guest
            - user_type: User type (guest or verified)
            - message: Message information
            - routing: Brand and instance routing information
            - template: Template and model information
            - model: Model information
            - llm_runtime: LLM runtime settings
            - trace_id: Trace ID for tracking
            - token_budgets: Token budgets (if available)
            
    Raises:
        ValidationError: If adapter cannot be built
    """
    start_time = time.time()
    
    # Generate trace ID if not provided
    trace_id = trace_id or getattr(message, 'trace_id', None) or str(uuid.uuid4())
    
    logger = get_context_logger(
        "message_adapter", 
        trace_id=trace_id,
        user_id=str(user.id) if user and hasattr(user, 'id') else None,
        session_id=str(session.id) if session and hasattr(session, 'id') else None,
        instance_id=str(instance.id) if instance and hasattr(instance, 'id') else None
    )
    
    # Validate required inputs
    if not session:
        logger.error("Session is required for message adapter")
        raise ValidationError(
            "Session is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="session"
        )
        
    if not user:
        logger.error("User is required for message adapter")
        raise ValidationError(
            "User is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="user"
        )
        
    if not instance:
        logger.error("Instance is required for message adapter")
        raise ValidationError(
            "Instance is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance"
        )
        
    if not message:
        logger.error("Message is required for message adapter")
        raise ValidationError(
            "Message is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="message"
        )
    
    # Determine user type and verification status
    is_guest = getattr(user, 'user_tier', "guest") == "guest"
    
    # Determine channel from message metadata
    channel = DEFAULT_CHANNEL
    if hasattr(message, 'meta_info') and message.meta_info and isinstance(message.meta_info, dict):
        channel = message.meta_info.get("channel", DEFAULT_CHANNEL)
    
    # Get template set info
    template_set = getattr(instance_config, 'template_set', None)
    
    # Extract session timestamps
    started_at = None
    last_message_at = None
    
    if hasattr(session, 'created_at') and session.created_at:
        started_at = session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at)
    
    if hasattr(session, 'last_message_at') and session.last_message_at:
        last_message_at = session.last_message_at.isoformat() if hasattr(session.last_message_at, 'isoformat') else str(session.last_message_at)
    
    # Get message content with fallbacks
    message_content = ""
    if hasattr(message, 'content'):
        message_content = message.content or ""
    
    # Initialize token_budgets
    token_budgets = None
    
    # Get token budgets if db is provided
    if db and session and template_set:
        try:
            token_budgets = get_token_budgets(db, str(session.id), trace_id)
        except Exception as e:
            logger.warning(f"Error getting token budgets: {str(e)}")
            # Continue without token budgets
    
    # Extract template functions with fallback
    template_functions = {}
    if template_set and hasattr(template_set, 'functions'):
        template_functions = template_set.functions or {}
    
    # Build adapter object
    adapter = {
        # Session information
        "session_id": str(session.id) if hasattr(session, 'id') else None,
        "session_context": {
            "started_at": started_at,
            "last_message_at": last_message_at
        },
        
        # User context
        "user_id": str(user.id) if hasattr(user, 'id') else None,
        "is_guest": is_guest,
        "user_type": "guest" if is_guest else "verified",
        
        # Message content
        "message": {
            "sender_user_id": str(user.id) if hasattr(user, 'id') else None,
            "content": message_content,
            "channel": channel,
            "message_id": str(message.id) if hasattr(message, 'id') else None
        },
        
        # Brand and instance context
        "routing": {
            "brand_id": str(instance.brand_id) if hasattr(instance, 'brand_id') else None,
            "instance_id": str(instance.id) if hasattr(instance, 'id') else None
        },
        
        # Template and model info
        "template": {
            "id": str(template_set.id) if template_set and hasattr(template_set, 'id') else None,
            "json": template_functions
        },
        
        # Model info
        "model": {
            "id": str(template_set.llm_model_id) if template_set and hasattr(template_set, 'llm_model_id') else None
        },
        
        # LLM runtime settings
        "llm_runtime": {
            "channel": channel,
            "accept_guest_users": getattr(instance, 'accept_guest_users', True)
        },
        
        # Tracking
        "trace_id": trace_id,
        
        # Build metadata
        "_meta": {
            "build_time": time.time() - start_time,
            "adapter_version": "1.0"
        }
    }
    
    # Add token budgets if available
    if token_budgets:
        adapter["token_budgets"] = token_budgets
    
    # Sanitize adapter
    sanitized_adapter = sanitize_adapter(adapter)
    
    # Validate adapter
    try:
        validate_adapter(sanitized_adapter, trace_id)
    except ValidationError as e:
        logger.warning(f"Adapter validation warning: {str(e)}")
        # Continue with best-effort adapter
    
    logger.info(f"Built message adapter in {time.time() - start_time:.3f}s")
    
    return sanitized_adapter