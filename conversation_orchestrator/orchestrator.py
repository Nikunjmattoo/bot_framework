"""
Main orchestrator entry point.

Receives adapter payload, orchestrates all steps, returns final response.
"""

import logging
import time
import uuid
from typing import Dict, Any

from conversation_orchestrator.exceptions import (
    OrchestratorError,
    ValidationError
)
from conversation_orchestrator.intent_detection.detector import detect_intents
from conversation_orchestrator.utils.logging import get_logger
from conversation_orchestrator.utils.validation import validate_adapter_payload

logger = get_logger(__name__)


async def process_message(adapter_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for conversation orchestrator.
    
    Orchestrates:
    1. Intent detection
    2. Brain processing (if needed)
    3. Response generation
    4. Post-processing
    
    Args:
        adapter_payload: Payload from message_handler with:
            - routing: {instance_id, brand_id}
            - message: {text, sender_user_id, channel, ...}
            - session_id
            - policy: {auth_state, can_call_tools, ...}
            - template: {json: {intent_detection: "...", response_generation: "..."}}
            - token_plan: {intent_detection: {input: 800, output: 150}, ...}
            - model, engine_ref, llm_runtime
            - plan_key
    
    Returns:
        Dict with:
            - text: Final response text
            - intents: Detected intents
            - self_response: Whether response was self-generated
            - token_usage: Token usage stats
            - latency_ms: Processing latency
            - trace_id: Trace ID for logging
    
    Raises:
        OrchestratorError: If processing fails
        ValidationError: If adapter payload is invalid
    """
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    logger.info(
        "orchestrator:started",
        extra={
            "trace_id": trace_id,
            "session_id": adapter_payload.get("session_id"),
            "channel": adapter_payload.get("message", {}).get("channel")
        }
    )
    
    try:
        # Validate adapter payload
        validate_adapter_payload(adapter_payload)
        
        # Step 1: Intent Detection
        intent_result = await detect_intents(adapter_payload, trace_id)
        
        logger.info(
            "orchestrator:intent_detection_complete",
            extra={
                "trace_id": trace_id,
                "intents_count": len(intent_result["intents"]),
                "intents": [i["intent_type"] for i in intent_result["intents"]],
                "self_response": intent_result.get("self_response", False)
            }
        )
        
        # Step 2: Check if self-response
        self_response = intent_result.get("self_response", False)
        response_text = intent_result.get("response_text")
        
        if self_response:
            # Self-respond: Use response_text from intent detection
            logger.info(
                "orchestrator:self_response_path",
                extra={
                    "trace_id": trace_id,
                    "response_length": len(response_text) if response_text else 0
                }
            )
            
            final_text = response_text or "I'm here to help!"
            
        else:
            # Brain-required: Pass to brain for processing
            logger.info(
                "orchestrator:brain_required_path",
                extra={
                    "trace_id": trace_id,
                    "intents": [i["intent_type"] for i in intent_result["intents"]]
                }
            )
            
            # TODO: Step 3 - Brain Processing
            # brain_result = process_brain(intent_result, adapter_payload, trace_id)
            
            # TODO: Step 4 - Response Generation
            # response_result = generate_response(brain_result, adapter_payload, trace_id)
            
            # Placeholder for now
            final_text = "Brain processing not implemented yet. Your intent has been detected and will be processed soon."
        
        # Calculate total latency
        total_latency_ms = (time.time() - start_time) * 1000
        
        # Build final result
        result = {
            "text": final_text,
            "intents": intent_result["intents"],
            "self_response": self_response,
            "reasoning": intent_result.get("reasoning"),
            "token_usage": intent_result.get("token_usage", {}),
            "latency_ms": total_latency_ms,
            "trace_id": trace_id
        }
        
        logger.info(
            "orchestrator:completed",
            extra={
                "trace_id": trace_id,
                "latency_ms": total_latency_ms,
                "self_response": self_response,
                "response_length": len(final_text),
                "tokens_total": intent_result.get("token_usage", {}).get("total", 0)
            }
        )
        
        return result
    
    except ValidationError as e:
        logger.error(
            "orchestrator:validation_error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_code": e.error_code
            }
        )
        raise
    
    except OrchestratorError as e:
        logger.error(
            "orchestrator:error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_code": e.error_code
            }
        )
        raise
    
    except Exception as e:
        logger.error(
            "orchestrator:unexpected_error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise OrchestratorError(
            message=f"Unexpected error: {str(e)}",
            error_code="UNEXPECTED_ERROR"
        ) from e