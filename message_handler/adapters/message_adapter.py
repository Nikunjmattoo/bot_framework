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

from message_handler.services.token_service import TokenManager
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.exceptions import ValidationError, ErrorCode
from message_handler.utils.validation import validate_metadata_field_size
from message_handler.utils.data_utils import sanitize_data
from message_handler.utils.datetime_utils import ensure_timezone_aware, format_iso_datetime
from message_handler.routing_plan import load_for_instance
from db.models.templates import TemplateModel

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
            - model: Model string from database
            - llm_runtime: Provider string from database
            - token_plan: Token plan (contains model info)
            - plan_key: Routing plan key
            - policy: Policy information
            - trace_id: Trace ID for tracking
            
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
    
    # Validate required inputs - CHECK THESE FIRST BEFORE ANY OTHER OPERATIONS
    if not session:
        logger.error("session is required for message adapter")
        raise ValidationError(
            "session is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="session"
        )
        
    if not user:
        logger.error("user is required for message adapter")
        raise ValidationError(
            "user is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="user"
        )
        
    if not instance:
        logger.error("instance is required for message adapter")
        raise ValidationError(
            "instance is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="instance"
        )
        
    if not message:
        logger.error("message is required for message adapter")
        raise ValidationError(
            "message is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="message"
        )
    
    if not db:
        logger.error("db is required for message adapter")
        raise ValidationError(
            "db is required for message adapter",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="db"
        )
    
    # Load routing plan for this instance
    instance_id_str = str(instance.id) if hasattr(instance, 'id') else None
    routing_plan = load_for_instance(instance_id_str)
    
    logger.debug(
        "Loaded routing plan",
        extra={
            "plan_key": routing_plan.get("plan_key")
        }
    )
    
    # Determine user type and verification status
    is_guest = getattr(user, 'user_tier', "guest") == "guest"
    
    # Determine channel from message metadata
    channel = DEFAULT_CHANNEL
    if hasattr(message, 'metadata_json') and message.metadata_json and isinstance(message.metadata_json, dict):
        channel = message.metadata_json.get("channel", DEFAULT_CHANNEL)
    
    # ✅ NEW ARCHITECTURE: Get template set and load model from primary template
    # Try to get template_set from the relationship first
    template_set = getattr(instance_config, 'template_set', None)
    
    # If relationship not loaded, try to query it by template_set_id
    if not template_set and hasattr(instance_config, 'template_set_id') and instance_config.template_set_id:
        from db.models.template_sets import TemplateSetModel
        template_set = db.query(TemplateSetModel).filter(
            TemplateSetModel.id == instance_config.template_set_id
        ).first()
    
    # STRICT: Fail if template_set missing
    if not template_set:
        logger.error("template_set is required in instance configuration")
        raise ValidationError(
            "template_set is required in instance configuration",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="template_set"
        )
    
    # Get functions mapping
    template_functions = getattr(template_set, 'functions', {})
    if not template_functions:
        logger.error(f"functions are required in template set {template_set.id}")
        raise ValidationError(
            "functions are required in template set",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="functions"
        )
    
    # Get the primary template key (use "response" or "compose" as primary, or first available)
    primary_template_key = (
        template_functions.get("response") or 
        template_functions.get("compose") or 
        next(iter(template_functions.values()))
    )
    
    logger.debug(f"Using primary template: {primary_template_key}")
    
    # Load the template from database
    primary_template = db.query(TemplateModel).filter(
        TemplateModel.template_key == primary_template_key,
        TemplateModel.is_active == True
    ).first()
    
    if not primary_template:
        logger.error(f"template not found: {primary_template_key}")
        raise ValidationError(
            f"template not found: {primary_template_key}",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="template",
            details={"template_key": primary_template_key}
        )
    
    # STRICT: Fail if llm_model missing from template
    if not hasattr(primary_template, 'llm_model') or not primary_template.llm_model:
        logger.error(f"llm_model is required in template {primary_template.id}")
        raise ValidationError(
            "llm_model is required in template",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="llm_model",
            details={"template_id": str(primary_template.id)}
        )
    
    llm_model = primary_template.llm_model
    
    # STRICT: Fail if api_model_name missing or empty/whitespace
    model_string = getattr(llm_model, 'api_model_name', None)
    if not model_string or not str(model_string).strip():
        logger.error(f"api_model_name is required in llm_model {llm_model.id}")
        raise ValidationError(
            "api_model_name is required in llm_model",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="api_model_name",
            details={"llm_model_id": str(llm_model.id)}
        )
    
    # STRICT: Fail if provider missing or empty/whitespace
    llm_runtime_string = getattr(llm_model, 'provider', None)
    if not llm_runtime_string or not str(llm_runtime_string).strip():
        logger.error(f"provider is required in llm_model {llm_model.id}")
        raise ValidationError(
            "provider is required in llm_model",
            error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
            field="provider",
            details={"llm_model_id": str(llm_model.id)}
        )
    
    logger.info(f"Loaded model from template '{primary_template_key}': model={model_string}, provider={llm_runtime_string}")
    
    # Extract session timestamps
    started_at = None
    last_message_at = None
    
    if hasattr(session, 'created_at') and session.created_at:
        started_at = format_iso_datetime(ensure_timezone_aware(session.created_at, field_name="session.created_at"))

    if hasattr(session, 'last_message_at') and session.last_message_at:
        last_message_at = format_iso_datetime(ensure_timezone_aware(session.last_message_at, field_name="session.last_message_at"))
    
    # Get message content with fallbacks
    message_content = ""
    if hasattr(message, 'content'):
        message_content = message.content or ""
    
    # Get token plan with auto-initialization
    token_plan = None
    
    # Try to get or initialize session-specific token plan
    if db and session:
        try:
            token_manager = TokenManager()
            
            # Try to get existing token plan
            token_plan_result = token_manager.get_token_plan(db, str(session.id), trace_id)
            
            if token_plan_result:
                # Found existing token plan
                token_plan = token_plan_result
                logger.debug(
                    "Using existing session token plan",
                    extra={"modules": list(token_plan.keys()) if isinstance(token_plan, dict) else None}
                )
            else:
                # No token plan exists - initialize it
                logger.info(
                    "No token plan found for new session, initializing",
                    extra={"session_id": str(session.id)}
                )
                
                # Initialize token plan for this session
                token_manager.initialize_session(
                    db=db,
                    session_id=str(session.id),
                    trace_id=trace_id
                )
                
                # Fetch the initialized plan
                token_plan = token_manager.get_token_plan(db, str(session.id), trace_id)
                
                if token_plan:
                    logger.info(
                        "Initialized token plan for session",
                        extra={
                            "session_id": str(session.id),
                            "modules": list(token_plan.keys()) if isinstance(token_plan, dict) else None
                        }
                    )
                else:
                    logger.warning(
                        "Token plan initialization failed",
                        extra={"session_id": str(session.id)}
                    )
                    
        except Exception as e:
            logger.warning(
                f"Error with token plan (get or initialize): {str(e)}",
                extra={"session_id": str(session.id) if session else None}
            )
    
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
        
        # Template info
        "template": {
            "id": str(template_set.id) if template_set and hasattr(template_set, 'id') else None,
            "json": template_functions
        },
        
        # ✅ Model and runtime from template's llm_model
        "model": model_string,
        "llm_runtime": llm_runtime_string,
        
        # Token plan (contains all model configuration)
        "token_plan": token_plan,
        
        # Plan key
        "plan_key": routing_plan.get("plan_key", "default"),
        
        # Policy (from instance)
        "policy": {
            "auth_state": "channel_verified" if not is_guest else "guest",
            "can_call_tools": not is_guest,
            "can_write_memory": False,
            "allow_pii_output": False
        },
        
        # Tracking
        "trace_id": trace_id,
        
        # Build metadata
        "_meta": {
            "build_time": time.time() - start_time,
            "adapter_version": "2.0",
            "routing_plan_key": routing_plan.get("plan_key")
        }
    }
    
    # Sanitize adapter
    sanitized_adapter = sanitize_adapter(adapter)
    
    # Validate adapter
    validate_adapter(sanitized_adapter, trace_id)
    
    logger.info(
        f"Built message adapter in {time.time() - start_time:.3f}s",
        extra={
            "plan_key": sanitized_adapter.get("plan_key"),
            "has_token_plan": bool(sanitized_adapter.get("token_plan")),
            "model": model_string,
            "runtime": llm_runtime_string
        }
    )
    
    return sanitized_adapter