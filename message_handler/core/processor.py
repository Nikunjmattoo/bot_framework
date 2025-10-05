"""
Core message processing logic.

This module provides the central processing logic for all messages
regardless of their channel, with orchestrator integration and
error handling.
"""
import uuid
import time
import json
from typing import Dict, Any, Optional, List, Union, cast
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError, 
    OrchestrationError, ErrorCode
)
from message_handler.services.message_service import save_inbound_message, save_outbound_message
from message_handler.services.token_service import update_token_usage, check_token_budget
from message_handler.adapters.message_adapter import build_message_adapter
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction
from message_handler.utils.error_handling import handle_database_error
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime

# Constants
DEFAULT_RESPONSE_TEXT = "I'm unable to process your request right now. Please try again later."
TOKEN_USAGE_FIELDS = ["prompt_in", "completion_out"]
MAX_CONTENT_LENGTH = 10000  # Maximum content length

# Orchestrator integration with graceful fallback
try:
    from conversation_orchestrator import process_message as process_orchestrator_message
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    
    def process_orchestrator_message(adapter: Dict[str, Any]) -> Dict[str, Any]:
        """Mock orchestrator for testing and fallback."""
        message_content = adapter.get("message", {}).get("content", "")
        return {
            "text": f"Mock response to: {message_content}",
            "llm_response": "This is a mock response for testing. The conversation orchestrator is not available.",
            "status": "mock",
            "timestamp": get_current_datetime().isoformat()
        }


def validate_content_length(content: str) -> str:
    """
    Validate and normalize content length.
    
    Args:
        content: Content to validate
    
    Returns:
        Normalized content
    
    Raises:
        ValidationError: If content exceeds maximum length
    """
    # Normalize content
    normalized_content = content.strip() if content else ""
    
    # Check length
    if len(normalized_content) > MAX_CONTENT_LENGTH:
        raise ValidationError(
            f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="content",
            details={"length": len(normalized_content), "max_length": MAX_CONTENT_LENGTH}
        )
    
    return normalized_content


def validate_orchestrator_response(
    response: Any, 
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate and normalize orchestrator response.
    
    Args:
        response: Orchestrator response
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Normalized response dictionary
    """
    logger = get_context_logger("processor", trace_id=trace_id)
    
    # Default fallback response
    fallback_response = {
        "text": DEFAULT_RESPONSE_TEXT,
        "error": "invalid_response",
        "timestamp": get_current_datetime().isoformat()
    }
    
    # Check if response exists
    if response is None:
        logger.error("Received empty response from orchestrator")
        return {"text": DEFAULT_RESPONSE_TEXT, "error": "empty_response"}
    
    # Check if response is a dictionary
    if not isinstance(response, dict):
        logger.error(f"Invalid orchestrator response type: {type(response)}")
        return {
            "text": DEFAULT_RESPONSE_TEXT, 
            "error": "invalid_response_type",
            "actual_type": str(type(response))
        }
    
    # Extract response text with fallbacks
    response_text = response.get("text", "")
    
    # If no text, try alternative fields
    if not response_text:
        for field in ["llm_response", "message", "content", "response"]:
            if field in response and response[field]:
                if isinstance(response[field], str):
                    response_text = response[field]
                    break
                elif isinstance(response[field], dict) and "content" in response[field]:
                    content = response[field]["content"]
                    if isinstance(content, str):
                        response_text = content
                        break
    
    # If still no text, use default
    if not response_text:
        logger.warning("No text found in orchestrator response, using default")
        response_text = DEFAULT_RESPONSE_TEXT
    
    # Create normalized response
    normalized_response = response.copy()
    normalized_response["text"] = response_text
    
    # Ensure timestamp is present
    if "timestamp" not in normalized_response:
        normalized_response["timestamp"] = get_current_datetime().isoformat()
    
    return normalized_response


def extract_token_usage(
    orchestrator_response: Dict[str, Any]
) -> Dict[str, int]:
    """
    Extract token usage information from orchestrator response.
    
    Args:
        orchestrator_response: Response from orchestrator
        
    Returns:
        Token usage dictionary with prompt_in and completion_out counts
    """
    token_usage = {}
    
    # Check if response has token usage information
    if orchestrator_response and "token_usage" in orchestrator_response and isinstance(orchestrator_response["token_usage"], dict):
        usage = orchestrator_response["token_usage"]
        
        # Extract standard fields
        for field in TOKEN_USAGE_FIELDS:
            if field in usage and isinstance(usage[field], (int, float)):
                token_usage[field] = int(usage[field])
    
    # Check for alternative usage format
    elif orchestrator_response and "usage" in orchestrator_response and isinstance(orchestrator_response["usage"], dict):
        usage = orchestrator_response["usage"]
        
        # Map from potential different field names
        field_mappings = {
            "prompt_in": ["prompt_tokens", "prompt", "input", "in"],
            "completion_out": ["completion_tokens", "completion", "output", "out"]
        }
        
        for target_field, source_fields in field_mappings.items():
            for source in source_fields:
                if source in usage and isinstance(usage[source], (int, float)):
                    token_usage[target_field] = int(usage[source])
                    break
    
    return token_usage


def process_core(
    db: Session,
    content: str,
    instance_id: str,
    user: Any,
    user_details: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    trace_id: Optional[str] = None,
    channel: str = "api",
    meta_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Core message processing logic, used by all channels.
    
    This function handles the complete lifecycle of message processing:
    1. Save the inbound user message
    2. Build the adapter for the orchestrator
    3. Process with the orchestrator
    4. Save the response message
    5. Update token usage statistics
    
    Args:
        db: Database session
        content: Message content
        instance_id: Instance ID
        user: User object with attached context
        user_details: User details dict (optional)
        idempotency_key: Idempotency key (optional)
        trace_id: Trace ID for logging (optional)
        channel: Channel (default: "api")
        meta_info: Additional metadata (optional)
        
    Returns:
        Dict containing:
            - message_id: ID of the inbound message
            - response: Dictionary with ID and content of the response message
            
    Raises:
        ValidationError: If inputs are invalid
        ResourceNotFoundError: If required resources not found
        OrchestrationError: If orchestration fails
        DatabaseError: If database operation fails
    """
    # Generate trace ID if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger(
        "processor", 
        trace_id=trace_id,
        user_id=str(user.id) if user and hasattr(user, 'id') else "unknown",
        session_id=str(user.session_id) if hasattr(user, 'session_id') else None,
        instance_id=instance_id,
        channel=channel
    )
    
    logger.info(f"Processing {channel} message")
    
    # Validate inputs
    try:
        # Validate content length
        normalized_content = validate_content_length(content)
        
        # Validate user
        if not user:
            logger.error("User is required")
            raise ValidationError(
                "User is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="user"
            )
            
        if not hasattr(user, 'session') or not user.session:
            logger.error("User session is required")
            raise ResourceNotFoundError(
                "User session is required",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="session"
            )
            
        if not hasattr(user, 'instance') or not user.instance:
            logger.error("User instance is required")
            raise ResourceNotFoundError(
                "User instance is required",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance"
            )
            
        if not hasattr(user, 'instance_config') or not user.instance_config:
            logger.error("Instance configuration is required")
            raise ResourceNotFoundError(
                "Instance configuration is required",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance_config"
            )
        
        # 1. Save inbound message
        inbound_message = save_inbound_message(
            db,
            session_id=user.session_id,
            user_id=user.id,
            instance_id=instance_id,
            content=normalized_content,
            channel=channel,
            meta_info=meta_info,
            idempotency_key=idempotency_key,
            trace_id=trace_id
        )
        
        message_saved_time = time.time()
        logger.debug(f"Inbound message saved in {message_saved_time - start_time:.3f}s")
        
        # 2. Build adapter for orchestrator
        adapter = build_message_adapter(
            session=user.session,
            user=user,
            instance=user.instance,
            instance_config=user.instance_config,
            message=inbound_message,
            trace_id=trace_id,
            db=db
        )
        
        adapter_built_time = time.time()
        logger.debug(f"Adapter built in {adapter_built_time - message_saved_time:.3f}s")
        
        # 3. Process with orchestrator
        orchestrator_response = None
        try:
            logger.info("Sending to orchestrator")
            
            if not ORCHESTRATOR_AVAILABLE:
                logger.warning("Orchestrator not available, using mock implementation")
            
            # Call orchestrator
            orchestrator_response = process_orchestrator_message(adapter)
            
            # Validate and normalize response
            orchestrator_response = validate_orchestrator_response(
                orchestrator_response,
                trace_id=trace_id
            )
            
        except Exception as e:
            logger.exception(f"Error processing message with orchestrator: {str(e)}")
            orchestrator_response = {
                "text": DEFAULT_RESPONSE_TEXT,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        orchestration_time = time.time()
        logger.debug(f"Orchestration completed in {orchestration_time - adapter_built_time:.3f}s")
        
        # Extract response text with fallback
        response_text = DEFAULT_RESPONSE_TEXT
        if orchestrator_response and isinstance(orchestrator_response, dict):
            response_text = orchestrator_response.get("text", DEFAULT_RESPONSE_TEXT)
        
        # 4. Save response message
        response_message = save_outbound_message(
            db,
            session_id=user.session_id,
            instance_id=instance_id,
            content=response_text,
            orchestrator_response=orchestrator_response,
            channel=channel,
            meta_info=meta_info,
            trace_id=trace_id
        )
        
        response_saved_time = time.time()
        logger.debug(f"Response message saved in {response_saved_time - orchestration_time:.3f}s")
        
        # 5. Update token usage if available
        token_usage = {}
        if orchestrator_response and isinstance(orchestrator_response, dict):
            token_usage = extract_token_usage(orchestrator_response)
            
        if token_usage:
            try:
                # Get module name from metadata or default to "compose"
                module_name = "compose"
                if isinstance(orchestrator_response, dict) and "module" in orchestrator_response:
                    module_name = orchestrator_response["module"]
                
                # Update token usage
                update_token_usage(
                    db,
                    str(user.session_id),
                    module_name,
                    token_usage,
                    trace_id=trace_id
                )
                
                logger.info(f"Updated token usage for module {module_name}: {token_usage}")
            except Exception as e:
                logger.warning(f"Error updating token usage: {str(e)}")
                # Continue processing even if token update fails
        
        # 6. Prepare result data - use str() for all UUIDs
        result_data = {
            "message_id": str(inbound_message.id),
            "response": {
                "id": str(response_message.id),
                "content": response_text
            }
        }
        
        # Add performance metrics
        total_time = time.time() - start_time
        result_data["_meta"] = {
            "processing_time_seconds": round(total_time, 3),
            "trace_id": trace_id,
            "timestamp": get_current_datetime().isoformat()
        }
        
        logger.info(f"Processed message successfully in {total_time:.3f}s")
        return result_data
        
    except ValidationError:
        # Re-raise validation errors
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except SQLAlchemyError as e:
        handle_database_error(e, "process_core", logger, trace_id=trace_id)
    except Exception as e:
        # Wrap other exceptions
        error_msg = f"Unexpected error in core processing: {str(e)}"
        logger.exception(error_msg)
        raise OrchestrationError(
            error_msg,
            error_code=ErrorCode.ORCHESTRATION_ERROR,
            original_exception=e,
            orchestrator="conversation_orchestrator"
        )