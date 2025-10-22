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
from message_handler.services.token_service import TokenManager
from message_handler.adapters.message_adapter import build_message_adapter
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction
from message_handler.utils.error_handling import handle_database_error
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime

from telemetry.langfuse_config import langfuse_client

DEFAULT_RESPONSE_TEXT = "I'm unable to process your request right now. Please try again later."
TOKEN_USAGE_FIELDS = ["prompt_in", "completion_out"]
MAX_CONTENT_LENGTH = 10000

try:
    from conversation_orchestrator import process_message as process_orchestrator_message
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    
    import os
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    
    if ENVIRONMENT == "production":
        def process_orchestrator_message(adapter: Dict[str, Any]) -> Dict[str, Any]:
            """Orchestrator unavailable - raise error in production."""
            raise OrchestrationError(
                "Conversation orchestrator service is not available",
                error_code=ErrorCode.ORCHESTRATION_ERROR,
                details={
                    "environment": ENVIRONMENT,
                    "adapter_trace_id": adapter.get("trace_id")
                }
            )
    else:
        def process_orchestrator_message(adapter: Dict[str, Any]) -> Dict[str, Any]:
            """Mock orchestrator for testing and development only."""
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"⚠️  Using MOCK orchestrator in {ENVIRONMENT} environment. "
                "Real orchestrator not available!"
            )
            
            message_content = adapter.get("message", {}).get("content", "")
            return {
                "text": f"[MOCK] Response to: {message_content}",
                "llm_response": "This is a mock response for testing. The conversation orchestrator is not available.",
                "status": "mock",
                "environment": ENVIRONMENT,
                "timestamp": get_current_datetime().isoformat()
            }

def validate_content_length(content: str) -> str:
    """Validate and normalize content length."""
    normalized_content = content.strip() if content else ""
    
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
    """Validate and normalize orchestrator response."""
    logger = get_context_logger("processor", trace_id=trace_id)
    
    fallback_response = {
        "text": DEFAULT_RESPONSE_TEXT,
        "error": "invalid_response",
        "timestamp": get_current_datetime().isoformat()
    }
    
    if response is None:
        logger.error("Received empty response from orchestrator")
        return {"text": DEFAULT_RESPONSE_TEXT, "error": "empty_response"}
    
    if not isinstance(response, dict):
        logger.error(f"Invalid orchestrator response type: {type(response)}")
        return {
            "text": DEFAULT_RESPONSE_TEXT, 
            "error": "invalid_response_type",
            "actual_type": str(type(response))
        }
    
    response_text = response.get("text", "")
    
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
    
    if not response_text:
        logger.warning("No text found in orchestrator response, using default")
        response_text = DEFAULT_RESPONSE_TEXT
    
    normalized_response = response.copy()
    normalized_response["text"] = response_text
    
    if "timestamp" not in normalized_response:
        normalized_response["timestamp"] = get_current_datetime().isoformat()
    
    return normalized_response


def extract_token_usage(orchestrator_response: Dict[str, Any]) -> Dict[str, int]:
    """Extract token usage information from orchestrator response."""
    token_usage = {}
    
    if orchestrator_response and "token_usage" in orchestrator_response and isinstance(orchestrator_response["token_usage"], dict):
        usage = orchestrator_response["token_usage"]
        
        for field in TOKEN_USAGE_FIELDS:
            if field in usage and isinstance(usage[field], (int, float)):
                token_usage[field] = int(usage[field])
    
    elif orchestrator_response and "usage" in orchestrator_response and isinstance(orchestrator_response["usage"], dict):
        usage = orchestrator_response["usage"]
        
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
    request_id: Optional[str] = None,
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
        request_id: Request ID for idempotency (optional)
        trace_id: Trace ID for logging (optional)
        channel: Channel (default: "api")
        meta_info: Additional metadata (optional)
        
    Returns:
        Dict containing message_id and response
    """
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
    
    trace = langfuse_client.trace(
        id=trace_id,
        name="message_processing",
        user_id=str(user.id) if user and hasattr(user, 'id') else None,
        session_id=str(user.session_id) if hasattr(user, 'session_id') else None,
        metadata={
            "instance_id": instance_id,
            "channel": channel,
            "brand_id": str(user.instance.brand_id) if hasattr(user, 'instance') and hasattr(user.instance, 'brand_id') else None,
            "user_tier": getattr(user, 'user_tier', 'unknown')
        },
        tags=[channel]
    )
    
    try:
        normalized_content = validate_content_length(content)
        
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
        
        span1 = trace.span(name="save_inbound_message")
        inbound_message = save_inbound_message(
            db,
            session_id=user.session_id,
            user_id=user.id,
            instance_id=instance_id,
            content=normalized_content,
            channel=channel,
            meta_info=meta_info,
            request_id=request_id,
            trace_id=trace_id
        )
        span1.end(metadata={"message_id": str(inbound_message.id)})
        
        message_saved_time = time.time()
        logger.debug(f"Inbound message saved in {message_saved_time - start_time:.3f}s")
        
        span2 = trace.span(name="build_adapter")
        adapter = build_message_adapter(
            session=user.session,
            user=user,
            instance=user.instance,
            instance_config=user.instance_config,
            message=inbound_message,
            trace_id=trace_id,
            db=db
        )
        span2.end(metadata={"adapter_size": len(str(adapter))})
        
        adapter_built_time = time.time()
        logger.debug(f"Adapter built in {adapter_built_time - message_saved_time:.3f}s")
        
        span3 = trace.span(name="orchestrator")
        orchestrator_response = None
        try:
            logger.info("Sending to orchestrator")
            
            if not ORCHESTRATOR_AVAILABLE:
                logger.warning("Orchestrator not available, using mock implementation")
            
            orchestrator_response = process_orchestrator_message(adapter)
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
        
        token_usage = extract_token_usage(orchestrator_response)
        
        span3.end(
            metadata={
                "tokens_in": token_usage.get("prompt_in", 0),
                "tokens_out": token_usage.get("completion_out", 0),
                "response_length": len(orchestrator_response.get("text", ""))
            }
        )
        
        orchestration_time = time.time()
        logger.debug(f"Orchestration completed in {orchestration_time - adapter_built_time:.3f}s")
        
        response_text = DEFAULT_RESPONSE_TEXT
        if orchestrator_response and isinstance(orchestrator_response, dict):
            response_text = orchestrator_response.get("text", DEFAULT_RESPONSE_TEXT)
        
        span4 = trace.span(name="save_outbound_message")
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
        span4.end(metadata={"response_id": str(response_message.id)})
        
        response_saved_time = time.time()
        logger.debug(f"Response message saved in {response_saved_time - orchestration_time:.3f}s")
        
        if token_usage:
            try:
                template_key = "default_template"
                function_name = "compose"
                
                if isinstance(orchestrator_response, dict):
                    if "template_key" in orchestrator_response:
                        template_key = orchestrator_response["template_key"]
                    if "function_name" in orchestrator_response:
                        function_name = orchestrator_response["function_name"]
                    elif "module" in orchestrator_response:
                        function_name = orchestrator_response["module"]
                
                token_manager = TokenManager()
                llm_model_id = None
                if user.instance_config and user.instance_config.template_set:
                    llm_model_id = str(user.instance_config.template_set.llm_model_id)

                token_manager.record_usage(
                    db,
                    session_id=str(user.session_id),
                    template_key=template_key,
                    function_name=function_name,
                    sent_tokens=token_usage.get("prompt_in", 0),
                    received_tokens=token_usage.get("completion_out", 0),
                    llm_model_id=llm_model_id,
                    trace_id=trace_id
                )                
                logger.info(f"Recorded token usage for {function_name}: {token_usage}")
            except Exception as e:
                logger.warning(f"Error recording token usage: {str(e)}")
        
        result_data = {
            "message_id": str(inbound_message.id),
            "response": {
                "id": str(response_message.id),
                "content": response_text
            }
        }
        
        total_time = time.time() - start_time
        result_data["_meta"] = {
            "processing_time_seconds": round(total_time, 3),
            "trace_id": trace_id,
            "timestamp": get_current_datetime().isoformat()
        }
        
        trace.update(
            output={
                "message_id": str(inbound_message.id),
                "response_id": str(response_message.id)
            },
            metadata={
                "processing_time_ms": round(total_time * 1000, 2)
            }
        )
        
        logger.info(f"Processed message successfully in {total_time:.3f}s")
        return result_data
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        trace.update(
            level="ERROR",
            status_message=f"Validation error: {str(e)}"
        )
        raise
    except ResourceNotFoundError as e:
        logger.warning(f"Resource not found: {str(e)}")
        trace.update(
            level="ERROR",
            status_message=f"Resource not found: {str(e)}"
        )
        raise
    except SQLAlchemyError as e:
        trace.update(
            level="ERROR",
            status_message=f"Database error: {str(e)}"
        )
        handle_database_error(e, "process_core", logger, trace_id=trace_id)
    except Exception as e:
        error_msg = f"Unexpected error in core processing: {str(e)}"
        logger.exception(error_msg)
        trace.update(
            level="ERROR",
            status_message=error_msg
        )
        raise OrchestrationError(
            error_msg,
            error_code=ErrorCode.ORCHESTRATION_ERROR,
            original_exception=e,
            orchestrator="conversation_orchestrator"
        )